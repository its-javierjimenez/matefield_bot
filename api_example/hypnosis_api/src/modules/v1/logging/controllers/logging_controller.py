import datetime
import logging
import typing

import fastapi
import faststream.rabbit.fastapi as faststream_rabbit_fastapi
from faststream import Logger as FaststreamLogger

from src.modules.v1.shared.schemas import queue as shared_queue_schema
from src.modules.v1.shared.services import rabbit_management_service
from ..queues.rabbit import queues as rabbit_queues
from ..schemas.logging import logging_schema
from ..services import logging_service


FASTAPI_LOGGER = logging.getLogger("uvicorn").getChild("v1.logging.controllers.settings")
FASTSTREAM_LOGGER : logging.Logger = FaststreamLogger("v1.logging.controllers.tasks")



ROUTER = faststream_rabbit_fastapi.RabbitRouter()



@ROUTER.get(
    "/count-remaining",
    response_model=shared_queue_schema.RemainingTasksResponse,
    responses={
        fastapi.status.HTTP_200_OK: {
            "description": "Remaining logging tasks retrieved successfully.",
        },
        fastapi.status.HTTP_502_BAD_GATEWAY: {
            "description": "Unable to query RabbitMQ management API.",
        },
    },
)
async def countRemainingTasks() -> shared_queue_schema.RemainingTasksResponse:
    try:
        return await rabbit_management_service.getArtifactRemaining(
            artifact="LOGGING",
            queues={
                "logging": rabbit_queues.HYPNOSIS_LOGGING_QUEUE.name,
            },
        )
    except rabbit_management_service.RabbitManagementError as exc:
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc



@ROUTER.put(
    "/events",
    response_model=logging_schema.LoggingCreateResponse,
    status_code=fastapi.status.HTTP_201_CREATED,
    responses={
        fastapi.status.HTTP_201_CREATED: {
            "description": "Logging event stored successfully.",
        },
        fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Failed to store the logging event.",
        },
    },
)
async def createLoggingEvent(
    event: typing.Annotated[logging_schema.LoggingSchema, fastapi.Body()],
) -> logging_schema.LoggingCreateResponse:
    FASTAPI_LOGGER.info(
        "[LOGGING][PIPELINE] Creating logging event for audio request %s",
        event.audioRequestID,
    )

    wasCreated = await logging_service.createPipelineEvent(event)

    if not wasCreated:
        FASTAPI_LOGGER.error(
            "[LOGGING][PIPELINE] Failed to create logging event for %s",
            event.audioRequestID,
        )
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create logging event.",
        )

    logging_service.scheduleLoggingWebhookDispatch(event)

    return logging_schema.LoggingCreateResponse(
        message="Logging event stored.",
        event=event,
    )



@ROUTER.put(
    "/events/webhooks",
    response_model=logging_schema.LoggingWebhookRegistrationResponse,
    status_code=fastapi.status.HTTP_201_CREATED,
    responses={
        fastapi.status.HTTP_201_CREATED: {
            "description": "Webhook registrado correctamente.",
        },
        fastapi.status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "El payload no cumple con el esquema requerido.",
        },
    },
)
async def registerLoggingWebhook(
    webhook: typing.Annotated[logging_schema.LoggingWebhookCreateRequest, fastapi.Body()],
) -> logging_schema.LoggingWebhookRegistrationResponse:
    FASTAPI_LOGGER.info(
        "[LOGGING][WEBHOOKS] Registrando webhook para el servicio %s",
        webhook.serviceName,
    )
    registered = await logging_service.registerLoggingWebhook(webhook)
    return logging_schema.LoggingWebhookRegistrationResponse(
        message="Webhook registrado correctamente.",
        webhook=registered,
    )



@ROUTER.get(
    "/events",
    response_model=logging_schema.LoggingEventsResponse,
    responses={
        fastapi.status.HTTP_200_OK: {
            "description": "Logging events fetched successfully.",
        },
        fastapi.status.HTTP_400_BAD_REQUEST: {
            "description": "Invalid date range supplied.",
        },
    },
)
async def getLoggingEvents(
    fromDate: typing.Annotated[int, fastapi.Query(description="Start of the time range (Unix timestamp in seconds).")],
    toDate: typing.Annotated[int, fastapi.Query(description="End of the time range (Unix timestamp in seconds).")],
    eventType: typing.Annotated[
        typing.Optional[str],
        fastapi.Query(
            description="Event type to filter on (omit to fetch all types).",
        ),
    ] = None,
) -> logging_schema.LoggingEventsResponse:
    if fromDate > toDate:
        FASTAPI_LOGGER.warning(
            "[LOGGING][PIPELINE] Invalid time range received: fromDate=%s toDate=%s",
            fromDate,
            toDate,
        )
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_400_BAD_REQUEST,
            detail="fromDate must be less than or equal to toDate.",
        )

    query: dict[str, typing.Any] = {
        "timestamp": {
            "$gte": fromDate,
            "$lte": toDate,
        },
    }

    if eventType:
        query["eventType"] = eventType.upper()

    FASTAPI_LOGGER.info(
        "[LOGGING][PIPELINE] Fetching events with query: %s",
        query,
    )

    events = await logging_service.getPipelineEventsFromDatabase(query)

    eventsList = [
        event.model_copy(deep=True)
        for event in events
    ]

    FASTAPI_LOGGER.info(
        "[LOGGING][PIPELINE] Found %d events",
        len(eventsList),
    )

    return logging_schema.LoggingEventsResponse(items=eventsList)


@ROUTER.get(
    "/events/user-summary",
    response_model=logging_schema.UserEventSummary,
    responses={
        fastapi.status.HTTP_200_OK: {
            "description": "User event summary fetched successfully.",
        },
        fastapi.status.HTTP_400_BAD_REQUEST: {
            "description": "Invalid date range supplied.",
        },
    },
)
async def getUserEventSummary(
    fromDate: int = fastapi.Query(..., description="Start of the time range (Unix timestamp in seconds)."),
    toDate: int = fastapi.Query(..., description="End of the time range (Unix timestamp in seconds)."),
    userEmail: str = fastapi.Query(..., description="User email to summarize."),
) -> logging_schema.UserEventSummary:
    """Return a per-user summary of counts per eventType in the given time range.

    Delegates aggregation to the logging service (which uses the repository aggregation pipeline).
    """
    if fromDate > toDate:
        FASTAPI_LOGGER.warning(
            "[LOGGING][USER-SUMMARY] Invalid time range received: fromDate=%s toDate=%s",
            fromDate,
            toDate,
        )
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_400_BAD_REQUEST,
            detail="fromDate must be less than or equal to toDate.",
        )

    summary = await logging_service.getUserEventSummary(userEmail=userEmail, fromDate=fromDate, toDate=toDate)
    return summary

@ROUTER.subscriber(
    queue=rabbit_queues.HYPNOSIS_LOGGING_QUEUE,
    exchange=rabbit_queues.shared_rabbit_exchanges.HYPNOSIS_EXCHANGE,
    title="Logging Task Subscriber",
    description="Subscriber for handling logging tasks from the logging queue."
)
async def logTask(
    task: typing.Dict[str, typing.Any],
    # msg: faststream_rabbit_fastapi.RabbitMessage #! hasta una proxima version no lo podremos usar
    #! Sino la alternativa sera un artefacto fuera de la API, ya que el bug es cuando hay routers anidados
):
    """
    Subscriber function to handle logging tasks from the logging queue.
    
    Message formats:
    - Mental API (NestJS): {"pattern": "routingKey", "data": TaskDTO} → sender=MENTAL-API
    - Hypnosis API (Python): TaskDTO directo con status=CREATED → sender=HYPNOSIS-API
    - Artefactos Python: TaskDTO directo con otro status → sender por origin_source/mapping
    - Caronte: DLQMessage
    """

    isFromNestJS = False
    isFromHypnosisAPI = False
    
    if "pattern" in task and "data" in task:
        # ? NestJS (Mental API) sends messages as {"pattern" : "routingKey" , "data": { TaskDTO }}
        FASTSTREAM_LOGGER.info("[LOGGING][PARSER] Detected NestJS message format - sender is MENTAL-API")
        isFromNestJS = True
        task = task["data"]
    elif isinstance(task, dict) and task.get("status", "").lower() == "created":
        # TaskDTO directo con status=CREATED viene de Hypnosis API (bulk create endpoints)
        FASTSTREAM_LOGGER.info("[LOGGING][PARSER] Detected direct TaskDTO with status=CREATED - sender is HYPNOSIS-API")
        isFromHypnosisAPI = True

    taskValidated, isFromCaronte = logging_service.validate_task_payload(task)

    if taskValidated is None:
        FASTSTREAM_LOGGER.error("[LOGGING][TASK] Failed to validate task as Caronte DLQMessage, Standard TaskDTO, or RetryTask.")
        return

    # Determine sender based on message origin
    if isFromNestJS:
        senderArtifact = "MENTAL-API"
    elif isFromHypnosisAPI:
        senderArtifact = "HYPNOSIS-API"
    else:
        origin_source = task.get("origin_source")
        senderArtifact = logging_service.determine_sender_artifact(taskValidated, isFromCaronte, origin_source)
    
    event_info = logging_service.extract_event_info(taskValidated, isFromCaronte, senderArtifact)
    
    # Si es NestJS pero el status NO es CREATED, el receiver es desconocido
    if isFromNestJS and taskValidated.status.lower() != "created":
        FASTSTREAM_LOGGER.warning(
            f"[LOGGING][PARSER] NestJS message with unexpected status '{taskValidated.status}' - receiver set to UNKNOWN"
        )
        event_info["receivedArtifact"] = "UNKNOWN"
    
    taskID = event_info["taskID"]
    artifactThatReceived = event_info["receivedArtifact"]

    if taskID is None:
        FASTSTREAM_LOGGER.error(
            "[LOGGING][TASK] Invalid task ID for logging event, aborting log creation."
        )
        return

    FASTSTREAM_LOGGER.info(
        f"[LOGGING][TASK] Received logging task for artifact {artifactThatReceived} with task ID: {taskID}"
    )

    eventToSave = logging_schema.LoggingSchema(
        audioRequestID=taskID,
        receivedArtifact=artifactThatReceived,
        senderArtifact=senderArtifact,
        queueRoutingKey=event_info["senderQueue"],
        timestamp=int(datetime.datetime.now(datetime.timezone.utc).timestamp()),
        eventType=event_info["eventType"],
        eventMessage=event_info["eventMessage"],
        userEmail=event_info["userEmail"],
        userLanguage=event_info["userLanguage"],
        userLevel=event_info["userLevel"],
        additionalInfo=event_info["additionalInfo"]
    )

    wasCreated = await logging_service.createPipelineEvent(eventToSave)

    if wasCreated:
        FASTSTREAM_LOGGER.info(
            f"[LOGGING][TASK] Successfully logged event for task ID: {taskID}"
        )
        logging_service.scheduleLoggingWebhookDispatch(eventToSave)
    else:
        FASTSTREAM_LOGGER.error(
            f"[LOGGING][TASK] Failed to log event for task ID: {taskID}"
        )