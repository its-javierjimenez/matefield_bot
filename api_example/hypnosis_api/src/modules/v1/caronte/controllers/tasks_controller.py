import typing
import datetime
import logging
import fastapi
import faststream.rabbit.fastapi as faststream_rabbit_fastapi
from faststream import Logger as FaststreamLogger

from hypnosis_schemas import abstract as hypnosis_abstract
from hypnosis_schemas import enums as hypnosis_enums
from hypnosis_utils.logger import getLogger
from src.modules.v1.shared.queues.rabbit import queues as shared_rabbit_queues
from src.modules.v1.shared.schemas import queue as shared_queue_schema
from src.modules.v1.shared.services import rabbit_management_service
from src.modules.v1.logging.services import logging_service
from ..services import tasks_service



FASTAPI_LOGGER = getLogger("v1.caronte.controllers.tasks")
FASTSTREAM_LOGGER : logging.Logger = FaststreamLogger("v1.caronte.controllers.tasks")



ROUTER = faststream_rabbit_fastapi.RabbitRouter(
    prefix="/tasks",
    tags=["tasks"],
)

@ROUTER.get(
    "/count-remaining",
    response_model=shared_queue_schema.RemainingTasksResponse,
    responses={
        fastapi.status.HTTP_200_OK: {
            "description": "Remaining Caronte tasks retrieved successfully.",
        },
        fastapi.status.HTTP_502_BAD_GATEWAY: {
            "description": "Unable to query RabbitMQ management API.",
        },
    },
)
async def countRemainingTasks() -> shared_queue_schema.RemainingTasksResponse:
    try:
        return await rabbit_management_service.getArtifactRemaining(
            artifact="CARONTE",
            queues={
                "deadLetter": shared_rabbit_queues.HYPNOSIS_DEAD_LETTER.name,
            },
        )
    except rabbit_management_service.RabbitManagementError as exc:
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@ROUTER.patch("/update/error")
async def updateTask(
    taskID: typing.Annotated[str, fastapi.Body()],
    errorStatus: typing.Annotated[hypnosis_abstract.ErrorData, fastapi.Body()],
    toStatus: typing.Annotated[
        typing.Literal[hypnosis_enums.TaskStatus.ERROR, hypnosis_enums.TaskStatus.CRITICAL],
        fastapi.Query()
    ] = hypnosis_enums.TaskStatus.CRITICAL
):
    FASTAPI_LOGGER.info(f"[CARONTE] Updating task: {taskID} to status '{toStatus}'")
    
    task = await tasks_service.getTaskById(taskID=taskID)
    
    await tasks_service.updateTask(
        task=task,
        toStatus=toStatus.value,
        newErrorStatus=errorStatus
    )

    FASTSTREAM_LOGGER.info(f"[CARONTE] Task {task.id} updated successfully to {toStatus}.")
    FASTSTREAM_LOGGER.info(f"[CARONTE] Creating Pipeline event for task {task.id}.")
    try:
        await logging_service.createPipelineEvent(
            logging_service.logging_schema.LoggingSchema(
                receivedArtifact="CARONTE",
                senderArtifact="CARONTE",
                queueRoutingKey=shared_rabbit_queues.HYPNOSIS_DEAD_LETTER.routing_key,
                audioRequestID=task.id,
                eventMessage=f"Task marked as '{toStatus}' by Caronte service.",
                additionalInfo={
                    "errorStatus" : errorStatus.model_dump(mode="json", by_alias=True, round_trip=True),
                },
                eventType=toStatus.upper(),
                userEmail=task.userData.email,
                userLanguage=task.userData.language,
                userLevel=task.userLevel,
                timestamp=int(datetime.datetime.now(datetime.timezone.utc).timestamp())
            )
        )
    except Exception as exc:
        FASTAPI_LOGGER.error(f"[CARONTE] Failed to create Pipeline event for task {task.id}: {exc}")
        

    return fastapi.responses.JSONResponse(
        status_code=fastapi.status.HTTP_200_OK,
        content={
            "message": f"Task {taskID} updated successfully to {toStatus}.",
        }
    )



@ROUTER.get("/dueTasksSinceHours/{hours}")
async def getDueTasksSinceHours(
    hours: typing.Annotated[int, fastapi.Path(ge=1)]
) -> list[hypnosis_abstract.TaskDTO]:
    FASTAPI_LOGGER.info(f"[CARONTE] Fetching due tasks since last {hours} hours.")
    
    dueTasks = await tasks_service.getDueTasksSinceHours(hours=hours)

    FASTAPI_LOGGER.info(f"[CARONTE] Retrieved {len(dueTasks)} due tasks since last {hours} hours.")

    return dueTasks