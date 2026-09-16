from hypnosis_utils.logger import getLogger
from hypnosis_schemas import abstract as hypnosis_abstract
from src.modules.v1.shared.services import mental_api_service



LOGGER = getLogger("v1.maker.services.tasks")



async def updateTask(
    task: hypnosis_abstract.TaskDTO,
    toStatus : str,
    newAudioMotive : hypnosis_abstract.AudioMotive | None = None,
    newErrorStatus : hypnosis_abstract.ErrorData | None = None,
):
    LOGGER.info(f"[MAKER] Updating task: {task.id}")
    
    taskToSend = task.model_copy(deep=True)

    errorStatusToSend = task.errorStatus
    errorStatusToSend.append(newErrorStatus) if newErrorStatus is not None else None

    LOGGER.info(f"[MAKER] Marking task {taskToSend.id} as '{toStatus}'")

    LOGGER.info(f"[MAKER] Step data {task.stepData}")

    await mental_api_service.markTaskAs(
        taskId=task.id,
        data=mental_api_service.UpdateAudioRequestData.model_validate(
            {
            **taskToSend.model_dump(mode="json", by_alias=True, round_trip=True),
            "status" : toStatus,
            "audioMotive": newAudioMotive if newAudioMotive is not None else task.audioMotive,
            "errorStatus": errorStatusToSend,
            }
        )
    )



async def getTaskById(
    taskID: str
) -> hypnosis_abstract.TaskDTO:
    LOGGER.info(f"[MAKER] Fetching task by ID: {taskID}")


    return await mental_api_service.getTaskById(
        taskId=taskID,
        model=hypnosis_abstract.TaskDTO
    )


async def getTasksInBulk(
    taskIDs: list[str]
) -> list[hypnosis_abstract.TaskDTO]:
    LOGGER.info(f"[MAKER] Fetching tasks in bulk for IDs: {taskIDs}")

    return await mental_api_service.getTasksByIds(
        taskIds=taskIDs,
        model=hypnosis_abstract.TaskDTO
    )