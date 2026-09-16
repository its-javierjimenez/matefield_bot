import typing
import logging
import fastapi
import faststream.rabbit.fastapi as faststream_rabbit_fastapi
from faststream import Logger as FaststreamLogger

from hypnosis_schemas import abstract as hypnosis_abstract
from hypnosis_schemas import enums as hypnosis_enums
from hypnosis_utils.logger import getLogger
from ..queues.rabbit import queues as rabbit_queues
from ..services import tasks_service
from src.modules.v1.shared.schemas import queue as shared_queue_schema
from src.modules.v1.shared.services import rabbit_management_service



FASTAPI_LOGGER = getLogger("v1.moderator.controllers.tasks")
FASTSTREAM_LOGGER : logging.Logger = FaststreamLogger("v1.moderator.controllers.tasks")



ROUTER = faststream_rabbit_fastapi.RabbitRouter(
    prefix="/tasks",
    tags=["tasks"],
)



NORMAL_TASKS_PUBLISHER = ROUTER.publisher(
    queue=rabbit_queues.HYPNOSIS_MODERATOR_NORMAL_TASKS,
    routing_key=rabbit_queues.HYPNOSIS_MODERATOR_NORMAL_TASKS.routing_key,
    exchange=rabbit_queues.shared_rabbit_exchanges.HYPNOSIS_EXCHANGE,
    content_type="application/json"
)

PRIORITY_TASKS_PUBLISHER = ROUTER.publisher(
    queue=rabbit_queues.HYPNOSIS_MODERATOR_PRIORITY_TASKS,
    routing_key=rabbit_queues.HYPNOSIS_MODERATOR_PRIORITY_TASKS.routing_key,
    exchange=rabbit_queues.shared_rabbit_exchanges.HYPNOSIS_EXCHANGE,
    content_type="application/json"
)


@ROUTER.put("/create")
async def createTask(
    task : typing.Annotated[hypnosis_abstract.TaskDTO, fastapi.Body(media_type="application/json")],
    priority: typing.Annotated[bool, fastapi.Query()] = False,
    source: typing.Annotated[str, fastapi.Header()] = "API",
) -> fastapi.responses.JSONResponse:

    FASTSTREAM_LOGGER.info(f"[MODERATOR] Creating task with priority={priority}: {task.id}")

    if priority:
        await PRIORITY_TASKS_PUBLISHER.publish(
            message=task,
            headers={"content_type": "application/json", "origin_source": source},
        )
        FASTSTREAM_LOGGER.info(f"[MODERATOR] Task published to priority queue: {task.id}")
        return fastapi.responses.JSONResponse(
            status_code=fastapi.status.HTTP_201_CREATED,
            content={
                "message": "Task published to priority queue.",
                "exchange": rabbit_queues.shared_rabbit_exchanges.HYPNOSIS_EXCHANGE.name,
                "queueRoutingKey": rabbit_queues.HYPNOSIS_MODERATOR_PRIORITY_TASKS.routing_key,
                "task": task.model_dump(mode="json", by_alias=True, round_trip=True)
            }
        )
    

    await NORMAL_TASKS_PUBLISHER.publish(
        message=task,
        headers={"content_type": "application/json", "origin_source": source},
    )
    FASTSTREAM_LOGGER.info(f"[MODERATOR] Task published to normal queue: {task.id}")
    return fastapi.responses.JSONResponse(
        status_code=fastapi.status.HTTP_201_CREATED,
        content={
            "message": "Task published to normal queue.",
            "exchange": rabbit_queues.shared_rabbit_exchanges.HYPNOSIS_EXCHANGE.name,
            "queueRoutingKey": rabbit_queues.HYPNOSIS_MODERATOR_NORMAL_TASKS.routing_key,
            "task": task.model_dump(mode="json", by_alias=True, round_trip=True)
        }
    )


@ROUTER.get(
    "/count-remaining",
    response_model=shared_queue_schema.RemainingTasksResponse,
    responses={
        fastapi.status.HTTP_200_OK: {
            "description": "Remaining moderator tasks retrieved successfully.",
        },
        fastapi.status.HTTP_502_BAD_GATEWAY: {
            "description": "Unable to query RabbitMQ management API.",
        },
    },
)
async def countRemainingTasks() -> shared_queue_schema.RemainingTasksResponse:
    try:
        return await rabbit_management_service.getArtifactRemaining(
            artifact="MODERATOR",
            queues={
                "normal": rabbit_queues.HYPNOSIS_MODERATOR_NORMAL_TASKS.name,
                "priority": rabbit_queues.HYPNOSIS_MODERATOR_PRIORITY_TASKS.name,
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
    markAs:  typing.Annotated[hypnosis_enums.TaskStatus, fastapi.Query()] = hypnosis_enums.TaskStatus.CREATED
) -> fastapi.responses.JSONResponse:
    FASTAPI_LOGGER.info(f"[MODERATOR] Creating bulk tasks with priority={priority}: {taskIDs}")

    allTasks = await tasks_service.getTasksInBulk(taskIDs)

    FASTAPI_LOGGER.info(f"[MODERATOR] {len(allTasks)} tasks fetched for bulk creation.")

    for task in allTasks:

        await tasks_service.updateTask(
            task=task,
            toStatus=markAs.value,
        )
        task.status = markAs

        if priority:
            await PRIORITY_TASKS_PUBLISHER.publish(
                message=task,
                headers={"content_type": "application/json", "origin_source": source},
            )
            FASTSTREAM_LOGGER.info(f"[MODERATOR] Task published to priority queue: {task.id}")
        else:
            await NORMAL_TASKS_PUBLISHER.publish(
                message=task,
                headers={"content_type": "application/json", "origin_source": source},
            )
            FASTSTREAM_LOGGER.info(f"[MODERATOR] Task published to normal queue: {task.id}")

    return fastapi.responses.JSONResponse(
        status_code=fastapi.status.HTTP_201_CREATED,
        content={
            "message": "Tasks created successfully.",
            "tasks": taskIDs,
            "exchange": rabbit_queues.shared_rabbit_exchanges.HYPNOSIS_EXCHANGE.name,
            "queueRoutingKey": rabbit_queues.HYPNOSIS_MODERATOR_PRIORITY_TASKS.routing_key if priority else rabbit_queues.HYPNOSIS_MODERATOR_NORMAL_TASKS.routing_key,
        }
    )



@ROUTER.patch("/update/error")
async def updateTask(
    task: typing.Annotated[hypnosis_abstract.TaskDTO, fastapi.Body()],
    errorStatus: typing.Annotated[hypnosis_abstract.ErrorData, fastapi.Body()],
    toStatus: typing.Annotated[
        typing.Literal[hypnosis_enums.TaskStatus.ERROR, hypnosis_enums.TaskStatus.REVIEW, hypnosis_enums.TaskStatus.REJECTED],
        fastapi.Query()
    ] = hypnosis_enums.TaskStatus.ERROR
) -> fastapi.responses.JSONResponse:
    
    FASTAPI_LOGGER.info(f"[MODERATOR] Updating task: {task.id}")

    await tasks_service.updateTask(
        task=task,
        toStatus=toStatus.value,
        newErrorStatus=errorStatus
    )

    return fastapi.responses.JSONResponse(
        status_code=fastapi.status.HTTP_200_OK,
        content={
            "message": "Task updated successfully.",
        }
    )


@ROUTER.post("/update/done")
async def updateTaskDone(
    task: typing.Annotated[hypnosis_abstract.TaskDTO, fastapi.Body(media_type="application/json")],
    toStatus: typing.Annotated[
        hypnosis_enums.TaskStatus,
        fastapi.Query()
    ] = hypnosis_enums.TaskStatus.APPROVED
) -> fastapi.responses.JSONResponse:
    
    FASTAPI_LOGGER.info(f"[MODERATOR] Marking task as done: {task.id} with status {toStatus}")

    updatedTask = await tasks_service.updateTask(
        task=task,
        toStatus=toStatus.value
    )

    return fastapi.responses.JSONResponse(
        status_code=fastapi.status.HTTP_200_OK,
        content={
            "message": "Task marked as done successfully.",
            "task": updatedTask.model_dump(mode="json", by_alias=True, round_trip=True)
        }
    )
