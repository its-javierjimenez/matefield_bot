import httpx
import tenacity
import anyio
import pydantic
import fastapi
import typing
import logging
from hypnosis_utils.logger import getLogger
from ..connections.apis import mental_api as mental_api_connections
from hypnosis_schemas import abstract as hypnosis_abstract



LOGGER = getLogger("v1.shared.services.mental_api")



class UpdateAudioRequestData(
    pydantic.BaseModel,
):
    model_config = pydantic.ConfigDict(
        extra="ignore",
        validate_by_alias=True,
        validate_by_name=True,
        serialize_by_alias=True,
    )

    status: str = pydantic.Field(description="The new status of the task")
    audioMotive: typing.Optional[hypnosis_abstract.AudioMotive] = pydantic.Field(default=None)
    errorStatus: typing.Optional[typing.List[hypnosis_abstract.ErrorData]] = pydantic.Field(default=None)
    stepData : hypnosis_abstract.StepData = pydantic.Field(default_factory=hypnosis_abstract.StepData)



class AudioElement(
    pydantic.BaseModel,
):
    model_config = pydantic.ConfigDict(
        extra="ignore",
        validate_by_alias=True,
        validate_by_name=True,
        serialize_by_alias=True,
    )

    audioUrl : typing.Optional[str] = pydantic.Field(
        default=None , alias="audioUrl" , description="The URL of the audio file to publish, its a CDN"
    )
    
    title: typing.Optional[str] = pydantic.Field(
        default=None , alias="title", description="The title of the audio file"
    )

    description: typing.Optional[str] = pydantic.Field(
        default=None , alias="description", description="The description of the audio file"
    )

    userLevel: typing.Optional[int] = pydantic.Field(
        default=None , alias="userLevel", description="The user level required to access the audio file"
    )

    formattedDuration: typing.Optional[str] = pydantic.Field(
        default=None , alias="formattedDuration", description="The formatted duration of the audio file"
    )



class UpdateAudioRequestAndPublishData(
    pydantic.BaseModel,
):
    model_config = model_config = pydantic.ConfigDict(
        extra="ignore",
        validate_by_alias=True,
        validate_by_name=True,
        serialize_by_alias=True,
    )

    audioRequestID: str = pydantic.Field(..., alias="audioRequestId", description="The unique identifier for the audio request")
    userID: str = pydantic.Field(..., alias="userId", description="The unique identifier for the user")
    status: str = pydantic.Field(..., description="The new status of the task")
    audioElement: AudioElement = pydantic.Field(..., description="The audio element details")
    stepData: hypnosis_abstract.StepData | None = pydantic.Field(
        default=None,
        description="Optional step data payload to persist alongside the task update",
    )



class BulkTasksResponse(pydantic.BaseModel):
    """Response model for bulk task retrieval"""
    model_config = pydantic.ConfigDict(
        extra="ignore",
        validate_by_alias=True,
        validate_by_name=True,
        serialize_by_alias=True,
    )
    
    audioRequests: typing.List[typing.Dict[str, typing.Any]] = pydantic.Field(
        ..., 
        description="List of audio requests/tasks"
    )
    count: int = pydantic.Field(
        ..., 
        description="Number of tasks found"
    )
    requested: int = pydantic.Field(
        ..., 
        description="Number of tasks requested"
    )



class UserAnalysisDTO(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(
        extra="ignore",
        validate_by_alias=True,
        validate_by_name=True,
        serialize_by_alias=True,
    )
    fullAnalysis: str
    userLevel: int



@tenacity.retry(
    sleep=anyio.sleep,
    stop=tenacity.stop_after_attempt(5),
    wait=tenacity.wait_random_exponential(multiplier=2, max=60),
    retry=tenacity.retry_if_exception_type(
        (httpx.HTTPError , fastapi.HTTPException)
    ),
    before_sleep=tenacity.before_sleep_log(LOGGER, logging.WARNING),
    reraise=True
)
async def markTaskAs(
    taskId: str,
    data: UpdateAudioRequestData,
) -> None:
    """
    Mark a task as completed, error, review, or pending, etc.

    args:
        taskId: The ID of the task to update.
        data: The data to update the task with.
        status: The new status of the task.
    """
    LOGGER.info(f"[MENTAL][API] Marking task {taskId} as '{data.status}'")

    toSend = data.model_dump(mode="json", by_alias=True, round_trip=True , exclude_none=True)

    LOGGER.info(f"[MENTAL][API] Sending update request for task {taskId}")

    response = await mental_api_connections.MENTAL_API_CLIENT.patch(
        f"/audioRequest/update/{taskId}",
        json=toSend
    )

    if not response.is_success:
        LOGGER.warning(f"Failed to mark task as '{data.status}': {response.text}")
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to mark task as '{data.status}': {response.text}"
        )

    LOGGER.info(f"[MENTAL][API] Successfully marked task {taskId} as '{data.status}'")

@tenacity.retry(
    sleep=anyio.sleep,
    stop=tenacity.stop_after_attempt(5),
    wait=tenacity.wait_random_exponential(multiplier=2, max=60),
    retry=tenacity.retry_if_exception_type(
        (httpx.HTTPError , fastapi.HTTPException)
    ),
    before_sleep=tenacity.before_sleep_log(LOGGER, logging.WARNING),
    reraise=True
)
async def publishAudioAndMarkTaskAs(
    data: UpdateAudioRequestAndPublishData,
) -> None:
    """
    Mark a task as completed, error, review, or pending, etc.

    args:
        taskId: The ID of the task to update.
        data: The data to update the task with.
        status: The new status of the task.
    """
    LOGGER.info(f"[MENTAL][API] Marking task {data.audioRequestID} as '{data.status}' with audio element: {data.audioElement}")

    payload = data.model_dump(mode="json", by_alias=True, round_trip=True , exclude_none=True)
    payload["audioElement"]["userLevel"] = str(data.audioElement.userLevel)  # Ensure userLevel is a string

    response = await mental_api_connections.MENTAL_API_CLIENT.patch(
        f"/audioRequest/updateAndPublishAudio/{data.audioRequestID}",
        json=payload,
    )

    if not response.is_success:
        LOGGER.warning(f"Failed to mark task as '{data.status}': {response.text}")
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to mark task as '{data.status}': {response.text}"
        )
    


@tenacity.retry(
    sleep=anyio.sleep,
    stop=tenacity.stop_after_attempt(5),
    wait=tenacity.wait_random_exponential(multiplier=2, max=60),
    retry=tenacity.retry_if_exception_type(
        (httpx.HTTPError , fastapi.HTTPException)
    ),
    before_sleep=tenacity.before_sleep_log(LOGGER, logging.WARNING),
    reraise=True
)
async def updateAudioElement(
    taskID: str,
    userID: str,
    audioElement: AudioElement,
) -> None:
    """
    Update the audio element of a task.

    args:
        taskID: The ID of the task to update.
        userID: The ID of the user who owns the task.
        audioElement: The new audio element details.
    """

    payload = {
        "audioRequestId": taskID,
        **audioElement.model_dump(mode="json", by_alias=True, round_trip=True, exclude_none=True)
    }

    LOGGER.info(f"[MENTAL][API] Sending update audio element request for task {taskID} with payload: {payload}")

    response = await mental_api_connections.MENTAL_API_CLIENT.patch(
        f"/audio/updateAudioItem/user/{userID}",
        json=payload
    )

    if not response.is_success:
        LOGGER.warning(f"Failed to update audio element for task {taskID}: {response.text}")
        raise fastapi.HTTPException(
            status_code=response.status_code,
            detail=f"Failed to update audio element for task {taskID}: {response.text}"
        )

    LOGGER.info(f"[MENTAL][API] Successfully updated audio element for task {taskID}")



getTaskModelType = typing.TypeVar("getTaskModelType" , bound=typing.Type[hypnosis_abstract.TaskDTO])
@tenacity.retry(
    sleep=anyio.sleep,
    stop=tenacity.stop_after_attempt(5),
    wait=tenacity.wait_random_exponential(multiplier=2, max=60),
    retry=tenacity.retry_if_exception_type(
        (httpx.HTTPError)
    ),
    before_sleep=tenacity.before_sleep_log(LOGGER, logging.WARNING),
    reraise=True
)
async def getTaskById(
    taskId: str,
    model: getTaskModelType
):
    """
    Get a task by its ID.

    args:
        taskId: The ID of the task to retrieve.
    
    returns:
        The task with the specified ID.
    """
    LOGGER.info(f"[MENTAL][API] Fetching task with ID: {taskId}")

    response = await mental_api_connections.MENTAL_API_CLIENT.get(
        f"/audioRequest/findByAudioRequestId/{taskId}"
    )

    if not response.is_success and response.status_code not in (fastapi.status.HTTP_204_NO_CONTENT, fastapi.status.HTTP_404_NOT_FOUND):
        LOGGER.warning(f"Failed to fetch task {taskId}: {response.status_code} - {response.text}")
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch task {taskId}: {response.text}"
        )
    
    if response.status_code in (fastapi.status.HTTP_204_NO_CONTENT, fastapi.status.HTTP_404_NOT_FOUND):
        LOGGER.info(f"[MENTAL][API] No content found for task {taskId}")
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_204_NO_CONTENT,
            detail=f"No content found for task {taskId}"
        )
    
    LOGGER.info(f"[MENTAL][API] Successfully fetched task data for {taskId}: {response.status_code}")

    try:
        taskData = response.json()
        task = model.model_validate(taskData)
        LOGGER.info(f"[MENTAL][API] Successfully fetched and validated task {taskId}")
        return task
    except pydantic.ValidationError as ve:
        LOGGER.error(f"Validation error while parsing task data for {taskId}: {ve}")
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Validation error while parsing task data for {taskId}: {ve}"
        )
    except Exception as e:
        LOGGER.error(f"Unexpected error while processing task data for {taskId}: {e}")
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error while processing task data for {taskId}: {e}"
        )



@tenacity.retry(
    sleep=anyio.sleep,
    stop=tenacity.stop_after_attempt(5),
    wait=tenacity.wait_random_exponential(multiplier=2, max=60),
    retry=tenacity.retry_if_exception_type(
        (httpx.HTTPError)
    ),
    before_sleep=tenacity.before_sleep_log(LOGGER, logging.WARNING),
    reraise=True
)
async def getTasksByIds(
    taskIds: typing.List[str],
    model: getTaskModelType | None = None
) -> typing.List[getTaskModelType] | BulkTasksResponse:
    """
    Get multiple tasks by their IDs.

    args:
        taskIds: List of task IDs to retrieve.
        model: Optional Pydantic model to validate and parse the tasks.
               If None, returns raw BulkTasksResponse.
    
    returns:
        List of validated tasks if model is provided, otherwise raw BulkTasksResponse.
    
    raises:
        fastapi.HTTPException: If the request fails or validation errors occur.
    """
    if not taskIds:
        LOGGER.warning("[MENTAL][API] No task IDs provided for bulk retrieval")
        return [] if model else BulkTasksResponse(audioRequests=[], count=0, requested=0)
    
    
    LOGGER.info(f"[MENTAL][API] Fetching {len(taskIds)} tasks by IDs")

    response = await mental_api_connections.MENTAL_API_CLIENT.post(
        "/audioRequest/findManyAudioRequests",
        headers=httpx.Headers({
            "Content-Type": "application/json",
            "Accept": "application/json",
        }),
        json={
            "ids": taskIds
        }
    )

    if not response.is_success and response.status_code not in (fastapi.status.HTTP_204_NO_CONTENT, fastapi.status.HTTP_404_NOT_FOUND):
        LOGGER.warning(f"Failed to fetch tasks in bulk: {response.status_code} - {response.text}")
        raise fastapi.HTTPException(
            status_code=response.status_code,
            detail=f"Failed to fetch tasks in bulk => {response.text}"
        )
    
    if response.status_code in (fastapi.status.HTTP_204_NO_CONTENT, fastapi.status.HTTP_404_NOT_FOUND):
        LOGGER.info("[MENTAL][API] Some or all requested tasks not found in bulk retrieval")
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_404_NOT_FOUND,
            detail=f"Some or all requested tasks not found in bulk retrieval => {response.text} | {response.status_code}"
        )
    
    try:
        responseData = response.json()
        bulkResponse = BulkTasksResponse.model_validate(responseData)
        
        LOGGER.info(
            f"[MENTAL][API] Successfully fetched {bulkResponse.count}/{bulkResponse.requested} tasks. "
            f"Requested: {len(taskIds)}, Found: {bulkResponse.count}"
        )

        if bulkResponse.count == 0 or (len(taskIds) != bulkResponse.count):
            LOGGER.warning(
                f"[MENTAL][API] Mismatch in requested vs found tasks. "
                f"Requested: {len(taskIds)}, Found: {bulkResponse.count}"
            )
            # find which taskIds were not found
            foundIds = {task.get("audioRequestId") for task in bulkResponse.audioRequests if "audioRequestId" in task}
            missingIds = set(taskIds) - foundIds
            LOGGER.warning(f"[MENTAL][API] Missing task IDs: {missingIds}")
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_404_NOT_FOUND,
                detail=f"Some or all requested tasks not found. Missing IDs:\n{missingIds}"
            )

        # If no model provided, return raw response
        if model is None:
            return bulkResponse
        
        # Validate and parse each task with the provided model
        typeAdapter = pydantic.TypeAdapter(list[model])
        try:
            validatedTasks = typeAdapter.validate_python(bulkResponse.audioRequests)
        except pydantic.ValidationError as ve:
            LOGGER.error(f"Validation error while parsing bulk response: {ve}")
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Validation error while parsing bulk response:\n{ve}"
            )

        LOGGER.info(
            f"[MENTAL][API] Successfully validated {len(validatedTasks)} tasks."
        )
        
        return validatedTasks
        
    except pydantic.ValidationError as ve:
        LOGGER.error(f"Validation error while parsing bulk response: {ve}")
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Validation error while parsing bulk response: {ve}"
        )
    except Exception as e:
        LOGGER.error(f"Unexpected error while processing bulk tasks: {e}")
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error while processing bulk tasks: {e}"
        )



@tenacity.retry(
    sleep=anyio.sleep,
    stop=tenacity.stop_after_attempt(5),
    wait=tenacity.wait_random_exponential(multiplier=2, max=60),
    retry=tenacity.retry_if_exception_type(
        (httpx.HTTPError)
    ),
    before_sleep=tenacity.before_sleep_log(LOGGER, logging.WARNING),
    reraise=True
)
async def getTasksByIdsRaw(
    taskIds: typing.List[str],
) -> BulkTasksResponse:
    """
    Get multiple tasks by their IDs without validation.
    Returns raw response from the API.

    args:
        taskIds: List of task IDs to retrieve.
    
    returns:
        BulkTasksResponse with raw task data.
    
    raises:
        fastapi.HTTPException: If the request fails.
    """
    return await getTasksByIds(taskIds=taskIds, model=None)



@tenacity.retry(
    sleep=anyio.sleep,
    stop=tenacity.stop_after_attempt(5),
    wait=tenacity.wait_random_exponential(multiplier=2, max=60),
    retry=tenacity.retry_if_exception_type(
        (httpx.HTTPError)
    ),
    before_sleep=tenacity.before_sleep_log(LOGGER, logging.WARNING),
    reraise=True
)
async def getAudioElement(
    taskID: str,
    userID: str,
) -> AudioElement:
    """
    Get the audio element of a task.
    args:
        taskID: The ID of the task to retrieve.
        userID: The ID of the user who owns the task.
    returns:
        The audio element of the task.
    """

    response = await mental_api_connections.MENTAL_API_CLIENT.get(
        f"/audio/getAudioItem/{userID}/{taskID}"
    )

    if not response.is_success and response.status_code not in (fastapi.status.HTTP_204_NO_CONTENT, fastapi.status.HTTP_404_NOT_FOUND):
        LOGGER.warning(f"Failed to fetch audio element for task {taskID}: {response.status_code} - {response.text}")
        raise fastapi.HTTPException(
            status_code=response.status_code,
            detail=f"Failed to fetch audio element for task {taskID}: {response.text}"
        )
    
    if response.status_code in (fastapi.status.HTTP_204_NO_CONTENT, fastapi.status.HTTP_404_NOT_FOUND):
        LOGGER.info(f"[MENTAL][API] No content found for audio element of task {taskID}")
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_404_NOT_FOUND,
            detail=f"No content found for audio element of task {taskID}"
        )
    
    LOGGER.info(f"[MENTAL][API] Successfully fetched audio element data for task {taskID}: {response.status_code}")
    
    try:
        audioData = response.json()
        audioElement = AudioElement.model_validate(audioData)
        LOGGER.info(f"[MENTAL][API] Successfully fetched and validated audio element for task {taskID}")
        return audioElement
    except pydantic.ValidationError as ve:
        LOGGER.error(f"Validation error while parsing audio element data for task {taskID}: {ve}")
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Validation error while parsing audio element data for task {taskID}: {ve}"
        )
    except Exception as e:
        LOGGER.error(f"Unexpected error while processing audio element data for task {taskID}: {e}")
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error while processing audio element data for task {taskID}: {e}"
        )
    

@tenacity.retry(
    sleep=anyio.sleep,
    stop=tenacity.stop_after_attempt(5),
    wait=tenacity.wait_random_exponential(multiplier=2, max=60),
    retry=tenacity.retry_if_exception_type(
        (httpx.HTTPError)
    ),
    before_sleep=tenacity.before_sleep_log(LOGGER, logging.WARNING),
    reraise=True
)
async def getDueTasksSinceHours(
    hours: int
) -> list[hypnosis_abstract.TaskDTO]:
    """
    Get tasks that are due since a certain number of hours.

    args:
        hours: The number of hours to look back for due tasks.
    
    returns:
        List of tasks that are due since the specified number of hours.
    """
    LOGGER.info(f"[MENTAL][API] Fetching due tasks since last {hours} hours.")

    response = await mental_api_connections.MENTAL_API_CLIENT.get(
        f"/audioRequest/getAudioRequestsOlderThanHours/{hours}"
    )

    if not response.is_success and response.status_code not in (fastapi.status.HTTP_204_NO_CONTENT, fastapi.status.HTTP_404_NOT_FOUND):
        LOGGER.warning(f"Failed to fetch due tasks since last {hours} hours: {response.status_code} - {response.text}")
        raise fastapi.HTTPException(
            status_code=response.status_code,
            detail=f"Failed to fetch due tasks since last {hours} hours: {response.text}"
        )
    
    if response.status_code in (fastapi.status.HTTP_204_NO_CONTENT, fastapi.status.HTTP_404_NOT_FOUND):
        LOGGER.info(f"[MENTAL][API] No due tasks found since last {hours} hours")
        return []
    
    try:
        tasksData = response.json()
        typeAdapter = pydantic.TypeAdapter(list[hypnosis_abstract.TaskDTO])
        tasks = typeAdapter.validate_python(tasksData["audiorequests"])
        LOGGER.info(f"[MENTAL][API] Successfully fetched and validated {len(tasks)} due tasks since last {hours} hours")
        return tasks
    except pydantic.ValidationError as ve:
        LOGGER.error(f"Validation error while parsing due tasks data: {ve}")
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Validation error while parsing due tasks data: {ve}"
        )
    except Exception as e:
        LOGGER.error(f"Unexpected error while processing due tasks data: {e}")
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error while processing due tasks data: {e}"
        )



@tenacity.retry(
    sleep=anyio.sleep,
    stop=tenacity.stop_after_attempt(5),
    wait=tenacity.wait_random_exponential(multiplier=2, max=60),
    retry=tenacity.retry_if_exception_type(
        (httpx.HTTPError)
    ),
    before_sleep=tenacity.before_sleep_log(LOGGER, logging.WARNING),
    reraise=True
)
async def getAllUserAnalysis(userID: str) -> typing.List[UserAnalysisDTO]:
    """
    Get all analysis for a user.

    args:
        userID: The ID of the user to retrieve analysis for.
    
    returns:
        A list of analysis for the user.
    """
    LOGGER.info(f"[MENTAL][API] Fetching analysis for user: {userID}")

    response = await mental_api_connections.MENTAL_API_CLIENT.get(
        f"audioRequest/getAnalysisByUser/{userID}"
    )

    if not response.is_success and response.status_code not in (fastapi.status.HTTP_204_NO_CONTENT, fastapi.status.HTTP_404_NOT_FOUND):
        LOGGER.warning(f"Failed to fetch analysis for user {userID}: {response.status_code} - {response.text}")
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch analysis for user {userID}: {response.text}"
        )
    
    if response.status_code in (fastapi.status.HTTP_204_NO_CONTENT, fastapi.status.HTTP_404_NOT_FOUND):
        LOGGER.info(f"[MENTAL][API] No analysis found for user {userID}")
        return []
    
    LOGGER.info(f"[MENTAL][API] Successfully fetched analysis for user {userID}")
    
    try:
        analysisData = response.json()
        typeAdapter = pydantic.TypeAdapter(list[UserAnalysisDTO])
        analysis = typeAdapter.validate_python(analysisData)
        return analysis
    except pydantic.ValidationError as ve:
        LOGGER.error(f"Validation error while parsing analysis data for user {userID}: {ve}")
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Validation error while parsing analysis data for user {userID}: {ve}"
        )
    except Exception as e:
        LOGGER.error(f"Unexpected error while processing analysis data for user {userID}: {e}")
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error while processing analysis data for user {userID}: {e}"
        )