import logging
import typing

import fastapi
import faststream.rabbit.fastapi as faststream_rabbit_fastapi
from faststream import Logger as FaststreamLogger
from hypnosis_schemas import abstract as hypnosis_abstract
from hypnosis_schemas import enums as hypnosis_enums
from hypnosis_utils.logger import getLogger

from src.config import ENVIRONMENT_SETTINGS
from src.modules.v1.shared.schemas import queue as shared_queue_schema
from src.modules.v1.shared.services import assets_service, rabbit_management_service

from ..queues.rabbit import queues as rabbit_queues
from ..services import tasks_service

FASTAPI_LOGGER = getLogger("v1.decorator.controllers.tasks")
FASTSTREAM_LOGGER : logging.Logger = FaststreamLogger("v1.decorator.controllers.tasks")



ROUTER = faststream_rabbit_fastapi.RabbitRouter(
    prefix="/tasks",
    tags=["tasks"],
)



NORMAL_TASKS_PUBLISHER = ROUTER.publisher(
    queue=rabbit_queues.HYPNOSIS_DECORATOR_NORMAL_TASKS,
    routing_key=rabbit_queues.HYPNOSIS_DECORATOR_NORMAL_TASKS.routing_key,
    exchange=rabbit_queues.shared_rabbit_exchanges.HYPNOSIS_EXCHANGE,
    content_type="application/json"
)

PRIORITY_TASKS_PUBLISHER = ROUTER.publisher(
    queue=rabbit_queues.HYPNOSIS_DECORATOR_PRIORITY_TASKS,
    routing_key=rabbit_queues.HYPNOSIS_DECORATOR_PRIORITY_TASKS.routing_key,
    exchange=rabbit_queues.shared_rabbit_exchanges.HYPNOSIS_EXCHANGE,
    content_type="application/json"
)

NORMAL_RETRY_TASKS_PUBLISHER = ROUTER.publisher(
    queue=rabbit_queues.HYPNOSIS_DECORATOR_NORMAL_RETRY_TASKS,
    routing_key=rabbit_queues.HYPNOSIS_DECORATOR_NORMAL_RETRY_TASKS.routing_key,
    exchange=rabbit_queues.shared_rabbit_exchanges.HYPNOSIS_EXCHANGE,
)

PRIORITY_RETRY_TASKS_PUBLISHER = ROUTER.publisher(
    queue=rabbit_queues.HYPNOSIS_DECORATOR_PRIORITY_RETRY_TASKS,
    routing_key=rabbit_queues.HYPNOSIS_DECORATOR_PRIORITY_RETRY_TASKS.routing_key,
    exchange=rabbit_queues.shared_rabbit_exchanges.HYPNOSIS_EXCHANGE,
)



@ROUTER.put("/create")
async def createTask(
    task : typing.Annotated[hypnosis_abstract.TaskDTO, fastapi.Body(media_type="application/json")],
    priority: typing.Annotated[bool, fastapi.Query()] = False
) -> fastapi.responses.JSONResponse:

    FASTSTREAM_LOGGER.info(f"[DECORATOR] Creating task with priority={priority}: {task.id}")

    if priority:
        await PRIORITY_TASKS_PUBLISHER.publish(
            message=task,
        )
        FASTSTREAM_LOGGER.info(f"[DECORATOR] Task published to priority queue: {task.id}")
        return fastapi.responses.JSONResponse(
            status_code=fastapi.status.HTTP_201_CREATED,
            content={
                "message": "Task published to priority queue.",
                "exchange": rabbit_queues.shared_rabbit_exchanges.HYPNOSIS_EXCHANGE.name,
                "queueRoutingKey": rabbit_queues.HYPNOSIS_DECORATOR_PRIORITY_TASKS.routing_key,
                "task": task.model_dump(mode="json", by_alias=True, round_trip=True)
            }
        )
    

    await NORMAL_TASKS_PUBLISHER.publish(
        message=task,
    )
    FASTSTREAM_LOGGER.info(f"[DECORATOR] Task published to normal queue: {task.id}")
    return fastapi.responses.JSONResponse(
        status_code=fastapi.status.HTTP_201_CREATED,
        content={
            "message": "Task published to normal queue.",
            "exchange": rabbit_queues.shared_rabbit_exchanges.HYPNOSIS_EXCHANGE.name,
            "queueRoutingKey": rabbit_queues.HYPNOSIS_DECORATOR_NORMAL_TASKS.routing_key,
            "task": task.model_dump(mode="json", by_alias=True, round_trip=True)
        }
    )



@ROUTER.get(
    "/count-remaining",
    response_model=shared_queue_schema.RemainingTasksResponse,
    responses={
        fastapi.status.HTTP_200_OK: {
            "description": "Remaining decorator tasks retrieved successfully.",
        },
        fastapi.status.HTTP_502_BAD_GATEWAY: {
            "description": "Unable to query RabbitMQ management API.",
        },
    },
)
async def countRemainingTasks() -> shared_queue_schema.RemainingTasksResponse:
    try:
        return await rabbit_management_service.getArtifactRemaining(
            artifact="DECORATOR",
            queues={
                "normal": rabbit_queues.HYPNOSIS_DECORATOR_NORMAL_TASKS.name,
                "priority": rabbit_queues.HYPNOSIS_DECORATOR_PRIORITY_TASKS.name,
                "retryNormal": rabbit_queues.HYPNOSIS_DECORATOR_NORMAL_RETRY_TASKS.name,
                "retryPriority": rabbit_queues.HYPNOSIS_DECORATOR_PRIORITY_RETRY_TASKS.name,
            },
        )
    except rabbit_management_service.RabbitManagementError as exc:
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc



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
    markAs:  typing.Annotated[hypnosis_enums.TaskStatus, fastapi.Query()] = hypnosis_enums.TaskStatus.EXPORTED
) -> fastapi.responses.JSONResponse:
    FASTAPI_LOGGER.info(f"[DECORATOR] Creating bulk tasks with priority={priority}: {taskIDs}")

    allTasks = await tasks_service.getTasksInBulk(taskIDs)

    FASTAPI_LOGGER.info(f"[DECORATOR] {len(allTasks)} tasks fetched for bulk creation.")

    for task in allTasks:

        await tasks_service.updateTask(
            task=task,
            toStatus=markAs.value
        )

        task.status = markAs

        if priority:
            await PRIORITY_TASKS_PUBLISHER.publish(
                message=task,
                headers={"origin_source": source, "content_type": "application/json"},
            )
            FASTSTREAM_LOGGER.info(f"[DECORATOR] Task published to priority queue: {task.id}")
        else:
            await NORMAL_TASKS_PUBLISHER.publish(
                message=task,
                headers={"origin_source": source, "content_type": "application/json"},
            )
            FASTSTREAM_LOGGER.info(f"[DECORATOR] Task published to normal queue: {task.id}")

    return fastapi.responses.JSONResponse(
        status_code=fastapi.status.HTTP_201_CREATED,
        content={
            "message": "Tasks created successfully.",
            "tasks": taskIDs,
            "exchange": rabbit_queues.shared_rabbit_exchanges.HYPNOSIS_EXCHANGE.name,
            "queueRoutingKey": rabbit_queues.HYPNOSIS_DECORATOR_PRIORITY_TASKS.routing_key if priority else rabbit_queues.HYPNOSIS_DECORATOR_NORMAL_TASKS.routing_key,
        }
    )



@ROUTER.patch("/update/error")
async def updateTask(
    task: typing.Annotated[hypnosis_abstract.TaskDTO, fastapi.Body()],
    errorStatus: typing.Annotated[hypnosis_abstract.ErrorData, fastapi.Body()],
    toStatus: typing.Annotated[
        typing.Literal[hypnosis_enums.TaskStatus.ERROR, hypnosis_enums.TaskStatus.REVIEW],
        fastapi.Query()
    ] = hypnosis_enums.TaskStatus.ERROR
):
    FASTAPI_LOGGER.info(f"[DECORATOR] Updating task: {task.id} to status '{toStatus}'")
    
    await tasks_service.updateTask(
        task=task,
        toStatus=toStatus.value,
        newErrorStatus=errorStatus
    )

    task.status = toStatus

    FASTSTREAM_LOGGER.info(f"[DECORATOR] Task {task.id} updated successfully to {toStatus}.")
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
    title: typing.Annotated[str, fastapi.Body()],
    duration: typing.Annotated[str, fastapi.Body()],
    toStatus: typing.Annotated[
        hypnosis_enums.TaskStatus,
        fastapi.Query()
    ] = hypnosis_enums.TaskStatus.COMPLETED
) -> fastapi.responses.JSONResponse:
    FASTAPI_LOGGER.info(f"[DECORATOR] Updating task: {task.id} to status '{toStatus}'")

    # ? Chequeamos que exista el archivo de audio
    # ? No usaremos los bytes asi que, solo verificamos que exista
    # ? Esto usará una peticion HEAD
    # ? Directamente levantará una excepcion si no existe el archivo
    # ? O si falla la conexión
    if not await assets_service.checkExportAudioExists(
        userID=task.userID,
        taskID=task.id
    ):
        FASTAPI_LOGGER.error(f"[DECORATOR] Audio file for task {task.id} not found in storage.")
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_404_NOT_FOUND,
            detail=f"Audio file for task {task.id} not found in storage."
        )

    FASTAPI_LOGGER.info(f"[DECORATOR] Archivo verificado en storage para task: {task.id}")

    FASTAPI_LOGGER.info(f"[DECORATOR] Getting audio URL for task: {task.id}")

    audioUrl = assets_service.getExportAudioPath(
        userID=task.userID,
        taskID=task.id,
        separated=False
    )

    FASTAPI_LOGGER.info(f"[DECORATOR] Audio URL obtained for task: {task.id}: {audioUrl}")
    FASTAPI_LOGGER.info(f"[DECORATOR] Updating and publishing task: {task.id} to status '{toStatus}' and audio URL: {audioUrl}")

    task.stepData = hypnosis_abstract.StepData(
        duration=duration,
        title=title,
    )

    await tasks_service.updateAndPublishTask(
        task=task,
        title=title,
        toStatus=toStatus.value,
        duration=duration,
        audioUrl=f"{ENVIRONMENT_SETTINGS.DECORATOR_SETTINGS.DECORATOR_AUDIOS_CDN}/{audioUrl}"
    )

    task.status = toStatus

    FASTAPI_LOGGER.info(f"[DECORATOR] Task {task.id} updated successfully to {toStatus}.")
    return fastapi.responses.JSONResponse(
        status_code=fastapi.status.HTTP_200_OK,
        content={
            "message": f"Task {task.id} updated successfully to {toStatus}.",
            "task": task.model_dump(mode="json", by_alias=True, round_trip=True)
        }
    )



@ROUTER.get(
    "/audioElement",
    response_class=fastapi.responses.JSONResponse,
    responses={
        fastapi.status.HTTP_200_OK: {
            "description": "Audio element retrieved successfully.",
            "model": tasks_service.mental_api_service.AudioElement
        },
        fastapi.status.HTTP_404_NOT_FOUND: {
            "description": "Audio element not found."
        },
        fastapi.status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Unprocessable entity."
        },
        fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Internal server error."
        }
    }
)
async def getAudioElement(
    userID: typing.Annotated[str, fastapi.Query()],
    taskID: typing.Annotated[str, fastapi.Query()]
):
    
    FASTAPI_LOGGER.info(f"[DECORATOR] Fetching audio element for task {taskID} and user {userID}")

    audioElement = await tasks_service.getAudioElement(
        userID=userID,
        taskID=taskID
    )

    FASTAPI_LOGGER.info(f"[DECORATOR] Audio element retrieved successfully for task {taskID} and user {userID}")

    return fastapi.responses.JSONResponse(
        status_code=fastapi.status.HTTP_200_OK,
        content=audioElement.model_dump(mode="json", by_alias=True, round_trip=True)
    )