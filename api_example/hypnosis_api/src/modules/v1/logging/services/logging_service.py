import asyncio
import logging
import typing
import aiocache

import httpx
import tenacity
from pydantic import ValidationError

from hypnosis_schemas import abstract as hypnosis_abstract
from hypnosis_schemas import enums as hypnosis_enums
from ..repository import (
    pipelines_events_repository,
    pipeline_events_webhooks_repository,
)
from ..schemas.logging import logging_schema
from src.config.environment import ENVIRONMENT_SETTINGS
from src.modules.v1.caronte.schemas.task import task_schema as caronte_task_schema
from src.modules.v1.maker.schemas import task as maker_task_schema


LOGGER = logging.getLogger("uvicorn").getChild("v1.logging.services.pipeline")
WEBHOOK_POST_TIMEOUT_SECONDS = 5
WEBHOOK_MAX_ATTEMPTS = 3
WEBHOOK_CONCURRENCY_LIMIT = 5
WEBHOOK_SIGNATURE_HEADER = "x-hypnosis-signature"
WEBHOOK_SIGNATURE_SECRET = (
    ENVIRONMENT_SETTINGS.SECURITY_SETTINGS.SECURITY_SIGNATURE_SECRET
)
ACTIVE_WEBHOOKS_CACHE = aiocache.SimpleMemoryCache()
ACTIVE_WEBHOOKS_CACHE_TTL_SECONDS = 30
ACTIVE_WEBHOOKS_CACHE_KEY = "logging:webhooks:active"
_activeWebhooksFetchLock = asyncio.Lock()


STATUS_ARTIFACT_MAP: dict[hypnosis_enums.TaskStatus, str] = {
    hypnosis_enums.TaskStatus.CREATED: "MAKER",
    hypnosis_enums.TaskStatus.RETRY_MAKER: "MAKER",
    hypnosis_enums.TaskStatus.RETRY_MODERATOR: "MODERATOR",
    hypnosis_enums.TaskStatus.RETRY_EXPORT: "EXPORT",
    hypnosis_enums.TaskStatus.RETRY_DECORATOR: "DECORATOR",
    hypnosis_enums.TaskStatus.PENDING: "EXPORT",
    hypnosis_enums.TaskStatus.EXPORTED: "DECORATOR",
    hypnosis_enums.TaskStatus.ERROR: "CARONTE",
    hypnosis_enums.TaskStatus.REVIEW: "SUPPORT",
    hypnosis_enums.TaskStatus.REJECTED: "SUPPORT",
    hypnosis_enums.TaskStatus.REBUFFED: "SUPPORT",
    hypnosis_enums.TaskStatus.CRITICAL: "DATABASE",
    hypnosis_enums.TaskStatus.COMPLETED: "MENTAL-API",
}

STATUS_SENDER_MAP: dict[hypnosis_enums.TaskStatus, str] = {
    hypnosis_enums.TaskStatus.CREATED: "MENTAL-API",
    hypnosis_enums.TaskStatus.RETRY_MAKER: "SUPPORT",
    hypnosis_enums.TaskStatus.RETRY_MODERATOR: "SUPPORT",
    hypnosis_enums.TaskStatus.RETRY_EXPORT: "SUPPORT",
    hypnosis_enums.TaskStatus.RETRY_DECORATOR: "SUPPORT",
    hypnosis_enums.TaskStatus.PENDING: "MAKER",
    hypnosis_enums.TaskStatus.EXPORTED: "EXPORT",
    hypnosis_enums.TaskStatus.COMPLETED: "DECORATOR",
    hypnosis_enums.TaskStatus.CRITICAL: "CARONTE",
    hypnosis_enums.TaskStatus.REVIEW: "MAKER",
    hypnosis_enums.TaskStatus.REJECTED: "MODERATOR",
    hypnosis_enums.TaskStatus.REBUFFED: "MODERATOR",
}

SOURCE_ARTIFACT_MAP: dict[str, str] = {
    "HYPNOSIS-MAKER": "MAKER",
    "MAKER": "MAKER",
    "HYPNOSIS-EXPORT": "EXPORT",
    "EXPORT": "EXPORT",
    "HYPNOSIS-DECORATOR": "DECORATOR",
    "DECORATOR": "DECORATOR",
    "HYPNOSIS-CARONTE": "CARONTE",
    "CARONTE": "CARONTE",
}


def validate_task_payload(
    task_data: typing.Dict[str, typing.Any]
) -> typing.Tuple[typing.Union[hypnosis_abstract.TaskDTO, caronte_task_schema.DLQMessage, None], bool]:
    """
    Validates the task payload against known schemas (Caronte DLQ, Standard Task, Retry Task).
    Returns the validated task object and a boolean indicating if it is from Caronte.
    """
    try:
        return caronte_task_schema.DLQMessage.model_validate(task_data), True
    except ValidationError:
        pass

    try:
        return hypnosis_abstract.TaskDTO.model_validate(task_data), False
    except ValidationError:
        pass

    try:
        # Try as RetryTask, but return the inner task
        retry_task = maker_task_schema.RetryTask.model_validate(task_data)
        return retry_task.task, False
    except ValidationError:
        pass

    return None, False


def determine_sender_artifact(
    task_validated: typing.Union[hypnosis_abstract.TaskDTO, maker_task_schema.retry_schema.RetryTask, caronte_task_schema.DLQMessage],
    is_caronte: bool,
    origin_source: typing.Optional[str] = None
) -> str:
    """
    Determines the artifact that sent the task based on status, error history, or Caronte metadata.
    """
    if origin_source:
        return str(origin_source).upper()

    if is_caronte:
        if isinstance(task_validated, caronte_task_schema.DLQMessage):
            split_from_source = task_validated.errorSourceService.split("-")
            return split_from_source[1].upper() if len(split_from_source) > 1 else task_validated.errorSourceService.upper()
        return "CARONTE"

    # Standard Task Logic
    try:
        status_enum = hypnosis_enums.TaskStatus(task_validated.status)
    except ValueError:
        status_enum = None
    
    # If it's a retry task (inferred from context or if we had a specific flag), we might want to return RETRY
    # But here we rely on status mapping first
    
    sender = STATUS_SENDER_MAP.get(status_enum)

    if sender is None and status_enum in (hypnosis_enums.TaskStatus.ERROR, hypnosis_enums.TaskStatus.REVIEW):
        latest_error = task_validated.errorStatus[-1] if getattr(task_validated, "errorStatus", None) else None
        error_source = getattr(latest_error, "source", None) if latest_error is not None else None
        if isinstance(error_source, str):
            sender = SOURCE_ARTIFACT_MAP.get(error_source.upper())

    if sender is None:
        extra_artifact = (task_validated.model_extra or {}).get("artifact") if hasattr(task_validated, "model_extra") else None
        sender = extra_artifact.upper() if isinstance(extra_artifact, str) else "UNKNOWN"

    return sender


def extract_event_info(
    task_validated: typing.Union[hypnosis_abstract.TaskDTO, maker_task_schema.retry_schema.RetryTask, caronte_task_schema.DLQMessage],
    is_caronte: bool,
    sender_artifact: str
) -> typing.Dict[str, typing.Any]:
    """
    Extracts relevant event information (ID, email, message, etc.) from the validated task.
    """
    info = {
        "taskID": None,
        "userEmail": None,
        "userLanguage": None,
        "userLevel": None,
        "eventMessage": None,
        "receivedArtifact": "UNKNOWN",
        "eventType": "UNKNOWN",
        "additionalInfo": {},
        "senderQueue": None
    }

    if is_caronte:
        info["receivedArtifact"] = "CARONTE"
        
        # Resolve the actual task dictionary (could be direct TaskDTO or wrapped in RetryTask)
        raw_task_data = task_validated.task if isinstance(task_validated.task, dict) else {}
        
        # Check if it's a RetryTask structure (has "task" key which is a dict with "_id")
        if "task" in raw_task_data and isinstance(raw_task_data["task"], dict) and "_id" in raw_task_data["task"]:
            artifact_source = raw_task_data["task"]
        else:
            # Assume it's a TaskDTO structure
            artifact_source = raw_task_data

        info["taskID"] = artifact_source.get("_id", None)
        
        info["eventType"] = task_validated.status.upper()
        info["additionalInfo"] = task_validated.additionalInfo
        info["senderQueue"] = task_validated.originalQueue
        
        user_payload = artifact_source.get("userData") if isinstance(artifact_source, dict) else None
        info["userEmail"] = user_payload.get("email") if isinstance(user_payload, dict) else None
        info["userLanguage"] = user_payload.get("language") if isinstance(user_payload, dict) else None
        
        info["eventMessage"] = (
            f"Queue {sender_artifact} sent task for artifact CARONTE with task ID: {info['taskID']}\n"
            f"Error was recorded: {task_validated.errorExceptionType}\n{task_validated.errorTraceback}"
        )

        level_candidate = artifact_source.get("userLevel") if isinstance(artifact_source, dict) else None
        if isinstance(level_candidate, int):
            info["userLevel"] = level_candidate
        elif isinstance(level_candidate, str) and level_candidate.isdigit():
            info["userLevel"] = int(level_candidate)

    else:
        try:
            status_enum = hypnosis_enums.TaskStatus(task_validated.status)
        except ValueError:
            status_enum = None

        info["eventType"] = status_enum.value.upper() if status_enum else str(task_validated.status).upper()
        info["taskID"] = task_validated.id
        info["userEmail"] = task_validated.userData.email
        info["userLanguage"] = task_validated.userData.language
        info["userLevel"] = task_validated.userLevel
        
        # Determine received artifact
        received = STATUS_ARTIFACT_MAP.get(status_enum)
        if received is None and status_enum in (hypnosis_enums.TaskStatus.ERROR, hypnosis_enums.TaskStatus.REVIEW):
            latest_error = task_validated.errorStatus[-1] if getattr(task_validated, "errorStatus", None) else None
            error_source = getattr(latest_error, "source", None) if latest_error is not None else None
            if isinstance(error_source, str):
                received = SOURCE_ARTIFACT_MAP.get(error_source.upper())
        
        if received is None:
             extra_artifact = (task_validated.model_extra or {}).get("artifact") if hasattr(task_validated, "model_extra") else None
             received = extra_artifact.upper() if isinstance(extra_artifact, str) else "UNKNOWN"
        
        info["receivedArtifact"] = received

        # Additional Info (Title)
        if status_enum == hypnosis_enums.TaskStatus.COMPLETED:
            title_value = None
            if getattr(task_validated, "stepData", None) is not None:
                title_value = getattr(task_validated.stepData, "title", None)

            if title_value is None and hasattr(task_validated, "model_extra"):
                extra_step_data = (task_validated.model_extra or {}).get("stepData")
                if isinstance(extra_step_data, dict):
                    title_value = extra_step_data.get("title")

            if title_value is not None:
                info["additionalInfo"]["title"] = title_value

        info["eventMessage"] = f"Queue received task for artifact {info['receivedArtifact']} from {sender_artifact} with task ID: {info['taskID']}"

    return info


async def _getCachedActiveWebhooks() -> tuple[logging_schema.LoggingWebhookSchema, ...]:
    """Obtiene webhooks activos aplicando TTL y lock para prevenir stampede.

    Args:
        None.

    Returns:
        tuple[LoggingWebhookSchema, ...]: Colección inmutable de webhooks activos.

    Raises:
        Exception: Si falla la consulta a la base de datos o el acceso al cache.
    """
    cachedRecords = await ACTIVE_WEBHOOKS_CACHE.get(ACTIVE_WEBHOOKS_CACHE_KEY)
    if cachedRecords is not None:
        return typing.cast(tuple[logging_schema.LoggingWebhookSchema, ...], cachedRecords)

    async with _activeWebhooksFetchLock:
        cachedRecords = await ACTIVE_WEBHOOKS_CACHE.get(ACTIVE_WEBHOOKS_CACHE_KEY)
        if cachedRecords is not None:
            return typing.cast(tuple[logging_schema.LoggingWebhookSchema, ...], cachedRecords)

        records = await pipeline_events_webhooks_repository.PIPELINE_EVENTS_WEBHOOKS_REPOSITORY_INSTANCE.listWebhooks(  # noqa: E501
            isActive=True,
        )
        cachedValue = tuple(records)
        await ACTIVE_WEBHOOKS_CACHE.set(
            ACTIVE_WEBHOOKS_CACHE_KEY,
            cachedValue,
            ttl=ACTIVE_WEBHOOKS_CACHE_TTL_SECONDS,
        )
        return cachedValue


async def _invalidateActiveWebhooksCache() -> None:
    """Elimina los webhooks activos del cache para forzar una recarga.

    Args:
        None.

    Returns:
        None.

    Raises:
        aiocache.exceptions.CacheException: Si no se puede eliminar la clave.
    """
    await ACTIVE_WEBHOOKS_CACHE.delete(ACTIVE_WEBHOOKS_CACHE_KEY)


async def getPipelineEventsFromDatabase(
    query: typing.Optional[dict[str, typing.Any]] = None,
) -> typing.Iterable[logging_schema.LoggingSchema]:
    """Devuelve los eventos históricos del pipeline almacenados en MongoDB.

    Args:
        query (dict[str, Any] | None): Filtro opcional para refinar la búsqueda.

    Returns:
        Iterable[LoggingSchema]: Eventos que cumplen con el filtro indicado.

    Raises:
        Exception: Si ocurre un error durante la consulta al repositorio.
    """
    LOGGER.info("[LOGGING][PIPELINE] Fetching pipeline events")

    queryToUse = query or {}

    return await pipelines_events_repository.PIPELINE_EVENTS_REPOSITORY.getEvents(
        query=queryToUse,
    )


async def createPipelineEvent(
    event: logging_schema.LoggingSchema,
) -> bool:
    """Persiste un evento de logging del pipeline en MongoDB.

    Args:
        event (LoggingSchema): Evento a almacenar.

    Returns:
        bool: True si el documento fue insertado correctamente.

    Raises:
        Exception: Si la inserción en la base de datos falla.
    """
    LOGGER.info(
        f"[LOGGING][PIPELINE] Creating pipeline event for audio request {event.audioRequestID}",
    )

    return await pipelines_events_repository.PIPELINE_EVENTS_REPOSITORY.createEvent(
        event,
    )


async def registerLoggingWebhook(
    subscription: logging_schema.LoggingWebhookCreateRequest,
) -> logging_schema.LoggingWebhookSchema:
    """Registra un nuevo webhook y forza invalidación del cache de listeners.

    Args:
        subscription (LoggingWebhookCreateRequest): Datos de la suscripción a crear.

    Returns:
        LoggingWebhookSchema: Documento persistido con los campos finales.

    Raises:
        Exception: Si la creación en base de datos o la invalidación fallan.
    """
    webhookDocument = logging_schema.LoggingWebhookSchema(
        **subscription.model_dump(),
    )
    stored = await pipeline_events_webhooks_repository.PIPELINE_EVENTS_WEBHOOKS_REPOSITORY_INSTANCE.createWebhook(
        webhookDocument,
    )
    await _invalidateActiveWebhooksCache()
    return stored


async def listLoggingWebhooks(
    isActive: typing.Optional[bool] = True,
) -> typing.Iterable[logging_schema.LoggingWebhookSchema]:
    """Lista los webhooks almacenados, usando cache para los activos.

    Args:
        isActive (bool | None): Bandera para filtrar por webhooks activos.

    Returns:
        Iterable[LoggingWebhookSchema]: Conjunto de webhooks según el filtro.

    Raises:
        Exception: Si el acceso al cache o a la base de datos falla.
    """
    if isActive is True:
        cached_records = await _getCachedActiveWebhooks()
        return [record.model_copy(deep=True) for record in cached_records]

    records = await pipeline_events_webhooks_repository.PIPELINE_EVENTS_WEBHOOKS_REPOSITORY_INSTANCE.listWebhooks(
        isActive=isActive,
    )
    return list(records)


async def getUserEventSummary(
    userEmail: str,
    fromDate: int,
    toDate: int,
) -> logging_schema.LoggingSchema | logging_schema.LoggingSchema:
    """Return aggregated counts per eventType for a specific user in the time range.

    Delegates aggregation to the repository and returns a Pydantic model.
    """
    try:
        counts = await pipelines_events_repository.PIPELINE_EVENTS_REPOSITORY.aggregateEventsByUser(
            userEmail=userEmail,
            fromDate=fromDate,
            toDate=toDate,
        )
    except Exception as e:
        LOGGER.exception("[LOGGING][SERVICE] Failed to aggregate user events")
        raise e

    # Build and return a lightweight object; controller will wrap into response model
    return logging_schema.UserEventSummary(
        userData=logging_schema.loggingEventSummaryUserData(userEmail=userEmail),
        events=counts,
        fromDate=fromDate,
        toDate=toDate,
    )


@tenacity.retry(
    sleep=asyncio.sleep,
    stop=tenacity.stop_after_attempt(WEBHOOK_MAX_ATTEMPTS),
    wait=tenacity.wait_exponential(multiplier=1, min=1, max=8),
    retry=tenacity.retry_if_exception_type(
        (httpx.HTTPError, httpx.TransportError, asyncio.TimeoutError),
    ),
    reraise=True,
)
async def _postWebhookWithRetry(
    webhook: logging_schema.LoggingWebhookSchema,
    payload: dict[str, typing.Any],
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
) -> None:
    """Envía un webhook con retries exponenciales y control de concurrencia.

    Args:
        webhook (LoggingWebhookSchema): Suscripción que define URL y servicio.
        payload (dict[str, Any]): Cuerpo serializado del evento.
        client (httpx.AsyncClient): Cliente HTTP compartido.
        semaphore (asyncio.Semaphore): Límite de conexiones simultáneas.

    Returns:
        None.

    Raises:
        httpx.HTTPError | httpx.TransportError | asyncio.TimeoutError:
            Propaga los errores cuando se agotan los reintentos configurados.
    """
    async with semaphore:
        response = await client.post(
            webhook.targetUrl,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "X-Hypnosis-Webhook": webhook.serviceName,
                WEBHOOK_SIGNATURE_HEADER: WEBHOOK_SIGNATURE_SECRET,
            },
        )
        response.raise_for_status()


async def _deliver_single_webhook(
    webhook: logging_schema.LoggingWebhookSchema,
    payload: dict[str, typing.Any],
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
) -> None:
    """Intenta enviar un webhook específico registrando logs de éxito o error.

    Args:
        webhook (LoggingWebhookSchema): Suscripción destino.
        payload (dict[str, Any]): Datos del evento.
        client (httpx.AsyncClient): Cliente HTTP reutilizable.
        semaphore (asyncio.Semaphore): Semáforo que limita concurrencia.

    Returns:
        None.

    Raises:
        None.
    """
    try:
        await _postWebhookWithRetry(webhook, payload, client, semaphore)
        LOGGER.debug(
            "[LOGGING][WEBHOOKS] Delivered event to %s", webhook.serviceName,
        )
    except Exception as exc:
        LOGGER.warning(
            "[LOGGING][WEBHOOKS] Failed to deliver event to %s: %s",
            webhook.serviceName,
            exc,
        )


async def dispatchLoggingEventToWebhooks(
    event: logging_schema.LoggingSchema,
) -> None:
    """Fan-out de un evento de logging hacia todos los webhooks activos.

    Args:
        event (LoggingSchema): Evento que se notificará a los suscriptores.

    Returns:
        None.

    Raises:
        None. Los fallos se registran en logs y cada tarea maneja sus errores.
    """
    try:
        webhooks = await listLoggingWebhooks(isActive=True)
    except Exception as exc:  # pragma: no cover
        LOGGER.exception("[LOGGING][WEBHOOKS] Failed to load webhooks: %s", exc)
        return

    if not webhooks:
        LOGGER.debug("[LOGGING][WEBHOOKS] No active webhooks to notify")
        return

    payload = event.model_dump(mode="json", by_alias=True, round_trip=True)
    semaphore = asyncio.Semaphore(WEBHOOK_CONCURRENCY_LIMIT)
    timeout = httpx.Timeout(WEBHOOK_POST_TIMEOUT_SECONDS)

    async with httpx.AsyncClient(timeout=timeout) as client:
        tasks = [
            _deliver_single_webhook(webhook, payload, client, semaphore)
            for webhook in webhooks
        ]
        await asyncio.gather(*tasks, return_exceptions=True)


def _log_webhook_task_result(task: asyncio.Task[typing.Any]) -> None:
    """Registra el estado final de la tarea que envía webhooks.

    Args:
        task (asyncio.Task[Any]): Tarea asociada al envío asíncrono.

    Returns:
        None.

    Raises:
        None.
    """
    if task.cancelled():
        LOGGER.warning("[LOGGING][WEBHOOKS] Dispatch task was cancelled")
        return
    if exception := task.exception():  # pragma: no cover
        LOGGER.error(
            "[LOGGING][WEBHOOKS] Dispatch task raised an exception: %s",
            exception,
        )


def scheduleLoggingWebhookDispatch(event: logging_schema.LoggingSchema) -> None:
    """Agenda el envío asíncrono de un evento a los webhooks activos.

    Args:
        event (LoggingSchema): Evento que se clonará y distribuirá.

    Returns:
        None.

    Raises:
        None. Si no se puede crear la tarea se registra en logs.
    """
    try:
        eventCopy = event.model_copy(deep=True)
        task = asyncio.create_task(dispatchLoggingEventToWebhooks(eventCopy))
        task.add_done_callback(_log_webhook_task_result)
    except RuntimeError as exc:  # pragma: no cover
        LOGGER.error("[LOGGING][WEBHOOKS] Unable to schedule dispatch: %s", exc)