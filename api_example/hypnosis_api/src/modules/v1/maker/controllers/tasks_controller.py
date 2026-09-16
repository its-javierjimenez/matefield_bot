import typing
import logging
import fastapi
import faststream.rabbit.fastapi as faststream_rabbit_fastapi
from faststream import Logger as FaststreamLogger

from hypnosis_schemas import abstract as hypnosis_abstract
from hypnosis_schemas import enums as hypnosis_enums
from hypnosis_schemas.artifacts import maker as hypnosis_maker_schemas
from hypnosis_utils.logger import getLogger
from src.modules.v1.shared.schemas import queue as shared_queue_schema
from src.modules.v1.shared.services import assets_service
from src.modules.v1.shared.services import rabbit_management_service
from src.modules.v1.shared.services import mental_api_service

from ..queues.rabbit import queues as rabbit_queues
from ..services import tasks_service



FASTAPI_LOGGER = getLogger("v1.maker.controllers.tasks")
FASTSTREAM_LOGGER : logging.Logger = FaststreamLogger("v1.maker.controllers.tasks")



ROUTER = faststream_rabbit_fastapi.RabbitRouter(
    prefix="/tasks",
    tags=["tasks"],
)



NORMAL_TASKS_PUBLISHER = ROUTER.publisher(
    queue=rabbit_queues.HYPNOSIS_MAKER_NORMAL_TASKS,
    routing_key=rabbit_queues.HYPNOSIS_MAKER_NORMAL_TASKS.routing_key,
    exchange=rabbit_queues.shared_rabbit_exchanges.HYPNOSIS_EXCHANGE,
    content_type="application/json"
)

PRIORITY_TASKS_PUBLISHER = ROUTER.publisher(
    queue=rabbit_queues.HYPNOSIS_MAKER_PRIORITY_TASKS,
    routing_key=rabbit_queues.HYPNOSIS_MAKER_PRIORITY_TASKS.routing_key,
    exchange=rabbit_queues.shared_rabbit_exchanges.HYPNOSIS_EXCHANGE,
    content_type="application/json"
)

NORMAL_RETRY_TASKS_PUBLISHER = ROUTER.publisher(
    queue=rabbit_queues.HYPNOSIS_MAKER_NORMAL_RETRY_TASKS,
    routing_key=rabbit_queues.HYPNOSIS_MAKER_NORMAL_RETRY_TASKS.routing_key,
    exchange=rabbit_queues.shared_rabbit_exchanges.HYPNOSIS_EXCHANGE,
    content_type="application/json"
)

PRIORITY_RETRY_TASKS_PUBLISHER = ROUTER.publisher(
    queue=rabbit_queues.HYPNOSIS_MAKER_PRIORITY_RETRY_TASKS,
    routing_key=rabbit_queues.HYPNOSIS_MAKER_PRIORITY_RETRY_TASKS.routing_key,
    exchange=rabbit_queues.shared_rabbit_exchanges.HYPNOSIS_EXCHANGE,
    content_type="application/json"
)



@ROUTER.put("/create")
async def createTask(
    task : typing.Annotated[hypnosis_abstract.TaskDTO, fastapi.Body(media_type="application/json")],
    priority: typing.Annotated[bool, fastapi.Query()] = False,
    source: typing.Annotated[str, fastapi.Header()] = "API"
) -> fastapi.responses.JSONResponse:

    FASTSTREAM_LOGGER.info(f"[MAKER] Creating task with priority={priority}: {task.id}")

    if priority:
        await PRIORITY_TASKS_PUBLISHER.publish(
            message=task,
            persist=True,
            headers={"content_type": "application/json", "origin_source": source},
        )
        FASTSTREAM_LOGGER.info(f"[MAKER] Task published to priority queue: {task.id}")
        return fastapi.responses.JSONResponse(
            status_code=fastapi.status.HTTP_201_CREATED,
            content={
                "message": "Task published to priority queue.",
                "exchange": rabbit_queues.shared_rabbit_exchanges.HYPNOSIS_EXCHANGE.name,
                "queueRoutingKey": rabbit_queues.HYPNOSIS_MAKER_PRIORITY_TASKS.routing_key,
                "task": task.model_dump(mode="json", by_alias=True, round_trip=True)
            }
        )

    await NORMAL_TASKS_PUBLISHER.publish(
        message=task,
        persist=True,
        headers={"content_type": "application/json", "origin_source": source},
    )
    FASTSTREAM_LOGGER.info(f"[MAKER] Task published to normal queue: {task.id}")
    return fastapi.responses.JSONResponse(
        status_code=fastapi.status.HTTP_201_CREATED,
        content={
            "message": "Task published to normal queue.",
            "exchange": rabbit_queues.shared_rabbit_exchanges.HYPNOSIS_EXCHANGE.name,
            "queueRoutingKey": rabbit_queues.HYPNOSIS_MAKER_NORMAL_TASKS.routing_key,
            "task": task.model_dump(mode="json", by_alias=True, round_trip=True)
        }
    )



@ROUTER.get(
    "/count-remaining",
    response_model=shared_queue_schema.RemainingTasksResponse,
    responses={
        fastapi.status.HTTP_200_OK: {
            "description": "Remaining maker tasks retrieved successfully.",
        },
        fastapi.status.HTTP_502_BAD_GATEWAY: {
            "description": "Unable to query RabbitMQ management API.",
        },
    },
)
async def countRemainingTasks() -> shared_queue_schema.RemainingTasksResponse:
    try:
        return await rabbit_management_service.getArtifactRemaining(
            artifact="MAKER",
            queues={
                "normal": rabbit_queues.HYPNOSIS_MAKER_NORMAL_TASKS.name,
                "priority": rabbit_queues.HYPNOSIS_MAKER_PRIORITY_TASKS.name,
                "retryNormal": rabbit_queues.HYPNOSIS_MAKER_NORMAL_RETRY_TASKS.name,
                "retryPriority": rabbit_queues.HYPNOSIS_MAKER_PRIORITY_RETRY_TASKS.name,
            },
        )
    except rabbit_management_service.RabbitManagementError as exc:
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc



class RetryTaskDTO(hypnosis_maker_schemas.RetryTask):
    task: str


@ROUTER.put(
    "/create/retry"
)
async def createRetryTask(
    retryTask : typing.Annotated[RetryTaskDTO, fastapi.Body(media_type="application/json")],
    priority: typing.Annotated[bool, fastapi.Query()] = False,
    source: typing.Annotated[str, fastapi.Header()] = "SUPPORT"
) -> fastapi.responses.JSONResponse:
    
    FASTSTREAM_LOGGER.info(f"[MAKER] Creating retry task with priority={priority}: {retryTask.task}")
    
    taskToSend = await tasks_service.getTaskById(retryTask.task)

    retryToSend = hypnosis_maker_schemas.RetryTask.model_validate(
        {
            "settings": retryTask.settings,
            "retry": retryTask.retry,
            "task": taskToSend
        }
    )

    await tasks_service.updateTask(
        task=taskToSend,
        toStatus="retrymaker",
    )
    taskToSend.status = "retrymaker"

    if priority:
        await PRIORITY_RETRY_TASKS_PUBLISHER.publish(
            message=retryToSend,
            persist=True,
            headers={"content_type": "application/json", "origin_source": source},
        )
        FASTSTREAM_LOGGER.info(f"[MAKER] Retry task published to priority queue: {retryToSend.task.id}")
        return fastapi.responses.JSONResponse(
            status_code=fastapi.status.HTTP_201_CREATED,
            content={
                "message": "Retry task published to priority queue.",
                "exchange": rabbit_queues.shared_rabbit_exchanges.HYPNOSIS_EXCHANGE.name,
                "queueRoutingKey": rabbit_queues.HYPNOSIS_MAKER_PRIORITY_RETRY_TASKS.routing_key,
                "task": retryToSend.model_dump(mode="json", by_alias=True, round_trip=True)
            }
        )

    await NORMAL_RETRY_TASKS_PUBLISHER.publish(
        message=retryToSend,
        persist=True,
        headers={"content_type": "application/json", "origin_source": source},
    )
    FASTSTREAM_LOGGER.info(f"[MAKER] Retry task published to normal queue: {retryToSend.task.id}")
    return fastapi.responses.JSONResponse(
        status_code=fastapi.status.HTTP_201_CREATED,
        content={
            "message": "Retry task published to normal queue.",
            "exchange": rabbit_queues.shared_rabbit_exchanges.HYPNOSIS_EXCHANGE.name,
            "queueRoutingKey": rabbit_queues.HYPNOSIS_MAKER_NORMAL_RETRY_TASKS.routing_key,
            "task": retryToSend.model_dump(mode="json", by_alias=True, round_trip=True)
        }
    )



@ROUTER.put(
    "/create/bulk",
    response_class=fastapi.responses.JSONResponse,
    responses={
        fastapi.status.HTTP_201_CREATED: {
            "description": "Tasks created successfully."
        },
        fastapi.status.HTTP_404_NOT_FOUND: {
            "description": "No tasks found to create."
        },
        fastapi.status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Unprocessable entity."
        },
        fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Internal server error."
        }
    }
)
async def createBulkTasks(
    taskIDs : typing.Annotated[typing.List[str], fastapi.Body(media_type="application/json")],
    priority: typing.Annotated[bool, fastapi.Query()] = False,
    source: typing.Annotated[str, fastapi.Header()] = "API",
    markAs : typing.Annotated[hypnosis_enums.TaskStatus, fastapi.Query()] = hypnosis_enums.TaskStatus.CREATED
) -> fastapi.responses.JSONResponse:
    FASTAPI_LOGGER.info(f"[MAKER] Creating bulk tasks with priority={priority}: {taskIDs}")

    allTasks = await tasks_service.getTasksInBulk(taskIDs)

    FASTAPI_LOGGER.info(f"[MAKER] {len(allTasks)} tasks fetched for bulk creation.")

    for task in allTasks:

        await tasks_service.updateTask(
            task=task,
            toStatus=markAs.value
        )

        task.status = markAs

        if priority:
            await PRIORITY_TASKS_PUBLISHER.publish(
                message=task,
                persist=True,
                headers={"content_type": "application/json", "origin_source": source},
            )
            FASTSTREAM_LOGGER.info(f"[MAKER] Task published to priority queue: {task.id}")
        else:
            await NORMAL_TASKS_PUBLISHER.publish(
                message=task,
                persist=True,
                headers={"content_type": "application/json", "origin_source": source},
            )
            FASTSTREAM_LOGGER.info(f"[MAKER] Task published to normal queue: {task.id}")

    return fastapi.responses.JSONResponse(
        status_code=fastapi.status.HTTP_201_CREATED,
        content={
            "message": "Tasks created successfully.",
            "tasks": taskIDs,
            "exchange": rabbit_queues.shared_rabbit_exchanges.HYPNOSIS_EXCHANGE.name,
            "queueRoutingKey": rabbit_queues.HYPNOSIS_MAKER_PRIORITY_TASKS.routing_key if priority else rabbit_queues.HYPNOSIS_MAKER_NORMAL_TASKS.routing_key,
        }
    )



@ROUTER.patch("/update/error")
async def updateTask(
    task: typing.Annotated[hypnosis_abstract.TaskDTO, fastapi.Body()],
    audioMotive: typing.Annotated[hypnosis_abstract.AudioMotive, fastapi.Body()],
    errorStatus: typing.Annotated[hypnosis_abstract.ErrorData, fastapi.Body()],
    toStatus: typing.Annotated[
        typing.Literal[hypnosis_enums.TaskStatus.ERROR, hypnosis_enums.TaskStatus.REVIEW],
        fastapi.Query()
    ] = hypnosis_enums.TaskStatus.ERROR
):
    FASTAPI_LOGGER.info(f"[MAKER] Updating task: {task.id} to status '{toStatus}'")
    
    if len(audioMotive.generatedSections) > 1:
        FASTAPI_LOGGER.info(f"[MAKER] The maker made {len(audioMotive.generatedSections)} sections for task {task.id}")
    
    
    await tasks_service.updateTask(
        task=task,
        toStatus=toStatus.value,
        newAudioMotive=audioMotive,
        newErrorStatus=errorStatus
    )

    task.status = toStatus

    FASTSTREAM_LOGGER.info(f"[MAKER] Task {task.id} updated successfully to {toStatus}.")
    return fastapi.responses.JSONResponse(
        status_code=fastapi.status.HTTP_200_OK,
        content={
            "message": f"Task {task.id} updated successfully to {toStatus}.",
            "task": task.model_dump(mode="json", by_alias=True, round_trip=True)
        }
    )



@ROUTER.patch(
    "/update/done",
    response_class=fastapi.responses.JSONResponse,
    responses={
        fastapi.status.HTTP_200_OK: {
            "description": "Task updated successfully."
        },
        fastapi.status.HTTP_404_NOT_FOUND: {
            "description": "file in storage not found."
        },
        fastapi.status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Unprocessable entity."
        },
        fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Internal server error."
        }
    }
)
async def updateTaskDone(
    task: typing.Annotated[hypnosis_abstract.TaskDTO, fastapi.Body()],
    audioMotive: typing.Annotated[hypnosis_abstract.AudioMotive, fastapi.Body()],
    toStatus: typing.Annotated[
        hypnosis_enums.TaskStatus,
        fastapi.Query()
    ] = hypnosis_enums.TaskStatus.PENDING
) -> fastapi.responses.JSONResponse:
    FASTAPI_LOGGER.info(f"[MAKER] Updating task: {task.id} to status '{toStatus}'")

    # ? Chequeamos que exista el archivo de audio
    # ? No usaremos los bytes asi que, solo verificamos que exista
    # ? Esto usará una peticion HEAD
    # ? Directamente levantará una excepcion si no existe el archivo
    # ? O si falla la conexión
    if not await assets_service.checkMakerZipExists(
        userID=task.userID,
        taskID=task.id
    ):
        FASTAPI_LOGGER.warning(f"[MAKER] Zip file not found for user '{task.userID}' and task '{task.id}'")
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_404_NOT_FOUND,
            detail=f"Zip file not found for user '{task.userID}' and task '{task.id}'"
        )

    FASTAPI_LOGGER.info("[MAKER] Archivo zip verificado en storage")

    await tasks_service.updateTask(
        task=task,
        toStatus=toStatus.value,
        newAudioMotive=audioMotive
    )

    task.status = toStatus

    FASTAPI_LOGGER.info(f"[MAKER] Task {task.id} updated successfully to {toStatus}.")
    return fastapi.responses.JSONResponse(
        status_code=fastapi.status.HTTP_200_OK,
        content={
            "message": f"Task {task.id} updated successfully to {toStatus}.",
            "task": task.model_dump(mode="json", by_alias=True, round_trip=True)
        }
    )



@ROUTER.get(
    "/analysis/{userID}",
    response_model=typing.List[mental_api_service.UserAnalysisDTO],
    responses={
        fastapi.status.HTTP_200_OK: {
            "description": "Analysis retrieved successfully."
        },
        fastapi.status.HTTP_404_NOT_FOUND: {
            "description": "No analysis found for the user."
        },
        fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Internal server error."
        }
    }
)
async def getUserAnalysis(
    userID: str
) -> typing.List[mental_api_service.UserAnalysisDTO]:
    FASTAPI_LOGGER.info(f"[MAKER] Fetching analysis for user: {userID}")
    
    analysis = await mental_api_service.getAllUserAnalysis(userID=userID)
    
    return analysis