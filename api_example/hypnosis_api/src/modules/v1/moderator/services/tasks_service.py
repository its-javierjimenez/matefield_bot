from hypnosis_schemas import abstract as hypnosis_abstract
from hypnosis_utils.logger import getLogger
from src.modules.v1.shared.services import mental_api_service



LOGGER = getLogger("v1.moderator.services.tasks")



async def updateTask(
    task: hypnosis_abstract.TaskDTO,
    toStatus : str,
    newErrorStatus : hypnosis_abstract.ErrorData | None = None,
):
    LOGGER.info(f"[MODERATOR] Updating task: {task.id}")
    
    taskToSend = task.model_copy(deep=True)
    taskToSend.status = toStatus
    taskToSend.errorStatus.append(
        newErrorStatus
    ) if newErrorStatus is not None else None

    LOGGER.info(f"[MODERATOR] Marking task {taskToSend.id} as '{toStatus}'")
    LOGGER.info(f"[MODERATOR] Step data {task.stepData}")
    await mental_api_service.markTaskAs(
        taskId=task.id,
        data=mental_api_service.UpdateAudioRequestData.model_validate(
            {
            **taskToSend.model_dump(mode="json", by_alias=True, round_trip=True),
            "audioMotive": taskToSend.audioMotive,
            }
        )
    )

    return taskToSend

async def getTasksInBulk(
    taskIDs: list[str]
) -> list[hypnosis_abstract.TaskDTO]:
    LOGGER.info(f"[MODERATOR] Fetching tasks in bulk for IDs: {taskIDs}")

    return await mental_api_service.getTasksByIds(
        taskIds=taskIDs,
        model=hypnosis_abstract.TaskDTO
    )
