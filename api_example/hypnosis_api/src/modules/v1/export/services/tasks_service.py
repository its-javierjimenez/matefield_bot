from hypnosis_schemas import abstract as hypnosis_abstract
from hypnosis_utils.logger import getLogger
from src.modules.v1.shared.services import mental_api_service



LOGGER = getLogger("v1.export.services.tasks")



async def updateTask(
    task: hypnosis_abstract.TaskDTO,
    toStatus : str,
    newErrorStatus : hypnosis_abstract.ErrorData | None = None,
):
    LOGGER.info(f"[EXPORT] Updating task: {task.id}")
    
    taskToSend = task.model_copy(deep=True)

    errorStatusToSend = taskToSend.errorStatus
    errorStatusToSend.append(newErrorStatus) if newErrorStatus is not None else None

    LOGGER.info(f"[EXPORT] Marking task {taskToSend.id} as '{toStatus}'")
    LOGGER.info(f"[EXPORT] Step data {task.stepData}")
    await mental_api_service.markTaskAs(
        taskId=task.id,
        data=mental_api_service.UpdateAudioRequestData.model_validate(
            {
            **taskToSend.model_dump(mode="json", by_alias=True, round_trip=True),
            "audioMotive": taskToSend.audioMotive,
            "status": toStatus,
            "errorStatus": errorStatusToSend,
            }
        )
    )



async def updateAndPublishTask(
    task: hypnosis_abstract.TaskDTO,
    toStatus: str,
    duration: str,
    audioUrl: str,
):
    LOGGER.info(f"[EXPORT] Updating and publishing task: {task.id} to status '{toStatus}' and audio URL: {audioUrl}")

    await mental_api_service.publishAudioAndMarkTaskAs(
        data=mental_api_service.UpdateAudioRequestAndPublishData(
            audioRequestId=task.id,
            userId=task.userID,
            status=toStatus,
            audioElement=mental_api_service.AudioElement(
                audioUrl=audioUrl,
                userLevel=task.userLevel,
                formattedDuration=duration
            )
        )
    )



async def getTasksInBulk(
    taskIDs: list[str]
) -> list[hypnosis_abstract.TaskDTO]:
    LOGGER.info(f"[EXPORT] Fetching tasks in bulk for IDs: {taskIDs}")

    return await mental_api_service.getTasksByIds(
        taskIds=taskIDs,
        model=hypnosis_abstract.TaskDTO
    )