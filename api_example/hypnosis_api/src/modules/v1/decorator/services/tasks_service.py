from hypnosis_schemas import abstract as hypnosis_abstract
from hypnosis_utils.logger import getLogger
from src.modules.v1.shared.services import mental_api_service



LOGGER = getLogger("v1.decorator.services.tasks")



async def updateTask(
    task: hypnosis_abstract.TaskDTO,
    toStatus : str,
    newErrorStatus : hypnosis_abstract.ErrorData | None = None,
):
    LOGGER.info(f"[DECORATOR] Updating task: {task.id}")
    
    taskToSend = task.model_copy(deep=True)

    errorStatusToSend = taskToSend.errorStatus
    errorStatusToSend.append(newErrorStatus) if newErrorStatus is not None else None

    LOGGER.info(f"[DECORATOR] Marking task {taskToSend.id} as '{toStatus}'")
    LOGGER.info(f"[DECORATOR] Step data {task.stepData}")
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
    title: str,
    toStatus: str,
    duration: str,
    audioUrl: str,
):
    LOGGER.info(f"[DECORATOR] Updating and publishing task: {task.id} to status '{toStatus}' and audio URL: {audioUrl}")

    await mental_api_service.publishAudioAndMarkTaskAs(
        data=mental_api_service.UpdateAudioRequestAndPublishData(
            audioRequestId=task.id,
            userId=task.userID,
            status=toStatus,
            audioElement=mental_api_service.AudioElement(
                audioUrl=audioUrl,
                title=title,
                userLevel=task.userLevel,
                formattedDuration=duration
            ),
            stepData=hypnosis_abstract.StepData(
                duration=duration,
                title=title,
            )
        )
    )



async def updateAudioElement(
    taskID: str,
    userID: str,
    title: str,
):
    
    LOGGER.info(f"[DECORATOR] Updating audio element for task {taskID}")
    LOGGER.info(f"[DECORATOR] New title: {title}")

    await mental_api_service.updateAudioElement(
        taskID=taskID,
        userID=userID,
        audioElement=mental_api_service.AudioElement(
            title=title
        )
    )



async def getTasksInBulk(
    taskIDs: list[str]
) -> list[hypnosis_abstract.TaskDTO]:
    LOGGER.info(f"[DECORATOR] Fetching tasks in bulk for IDs: {taskIDs}")

    return await mental_api_service.getTasksByIds(
        taskIds=taskIDs,
        model=hypnosis_abstract.TaskDTO
    )



async def getAudioElement(
    userID: str,
    taskID: str,
) -> mental_api_service.AudioElement:
    LOGGER.info(f"[DECORATOR] Fetching audio element for task {taskID} and user {userID}")

    return await mental_api_service.getAudioElement(
        taskID=taskID,
        userID=userID
    )