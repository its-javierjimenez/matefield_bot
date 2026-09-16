from hypnosis_schemas import abstract as hypnosis_abstract
from hypnosis_utils.logger import getLogger
from src.modules.v1.shared.services import mental_api_service

LOGGER = getLogger("v1.caronte.services.tasks")



async def getTaskById(
    taskID: str
) -> hypnosis_abstract.TaskDTO:
    LOGGER.info(f"[CARONTE] Fetching task by ID: {taskID}")


    return await mental_api_service.getTaskById(
        taskId=taskID,
        model=hypnosis_abstract.TaskDTO
    )



async def updateTask(
    task: hypnosis_abstract.TaskDTO,
    toStatus: str,
    newErrorStatus: hypnosis_abstract.ErrorData | None = None,
):
    LOGGER.info(f"[CARONTE] Updating task: {task.id}")
    LOGGER.info(f"[CARONTE] Marking task {task.id} as '{toStatus}'")
    newErrorStatus = task.errorStatus + [newErrorStatus] if newErrorStatus is not None else task.errorStatus

    await mental_api_service.markTaskAs(
        taskId=task.id,
        data=mental_api_service.UpdateAudioRequestData.model_validate(
            {
            **task.model_dump(mode="json", by_alias=True, round_trip=True),
            "status" : toStatus,
            "errorStatus": newErrorStatus,
            }
        )
    )



async def getDueTasksSinceHours(
    hours: int
) -> list[hypnosis_abstract.TaskDTO]:
    LOGGER.info(f"[CARONTE] Fetching due tasks since last {hours} hours.")

    return await mental_api_service.getDueTasksSinceHours(
        hours=hours,
    )