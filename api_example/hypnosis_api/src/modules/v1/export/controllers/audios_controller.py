import typing
import fastapi
from hypnosis_utils.logger import getLogger
from src.modules.v1.shared.services import assets_service



LOGGER = getLogger("v1.export.controllers.audios")



ROUTER = fastapi.APIRouter(
    prefix="/audios",
    tags=["audios", "assets"],
)



@ROUTER.head(
    "/{userId}/{taskId}",
    description="Check if an export audio exists for the given user and task.",
    responses={
        fastapi.status.HTTP_200_OK: {"description": "Audio file exists."},
        fastapi.status.HTTP_204_NO_CONTENT: {"description": "Audio file does not exist."},
        fastapi.status.HTTP_404_NOT_FOUND: {"description": "Audio file not found."},
        fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error."}
    }
)
async def checkAudioExists(
    userId: typing.Annotated[str, fastapi.Path(description="The user ID")],
    taskId: typing.Annotated[str, fastapi.Path(description="The task ID")],
) -> fastapi.Response:
    """Check if an export audio file exists in storage."""
    LOGGER.info(f"[EXPORT][AUDIOS] Checking audio existence for userId={userId}, taskId={taskId}")
    
    await assets_service.checkExportAudioExists(userID=userId, taskID=taskId)
    
    return fastapi.Response(status_code=fastapi.status.HTTP_200_OK)



@ROUTER.get(
    "/{userId}/{taskId}",
    description="Download an export audio file for the given user and task.",
    response_class=fastapi.responses.StreamingResponse,
    responses={
        fastapi.status.HTTP_200_OK: {
            "content": {"audio/mpeg": {}},
            "description": "Audio file retrieved successfully."
        },
        fastapi.status.HTTP_204_NO_CONTENT: {"description": "Audio file does not exist."},
        fastapi.status.HTTP_404_NOT_FOUND: {"description": "Audio file not found."},
        fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error."}
    }
)
async def getAudio(
    userId: typing.Annotated[str, fastapi.Path(description="The user ID")],
    taskId: typing.Annotated[str, fastapi.Path(description="The task ID")],
) -> fastapi.responses.StreamingResponse:
    """Download an export audio file from storage."""
    LOGGER.info(f"[EXPORT][AUDIOS] Downloading audio for userId={userId}, taskId={taskId}")
    
    audioIter, response = await assets_service.getExportAudio(userID=userId, taskID=taskId)
    
    return fastapi.responses.StreamingResponse(
        content=audioIter,
        status_code=fastapi.status.HTTP_200_OK,
        media_type="audio/mpeg",
        headers={
            "content-type": "audio/mpeg",
            "Content-Disposition": "attachment; filename=audio.mp3"
        },
        background=fastapi.BackgroundTasks([response.aclose])
    )



@ROUTER.put(
    "/{userId}/{taskId}",
    description="Upload an export audio file for the given user and task.",
    response_class=fastapi.responses.JSONResponse,
    responses={
        fastapi.status.HTTP_201_CREATED: {"description": "Audio file uploaded successfully."},
        fastapi.status.HTTP_400_BAD_REQUEST: {"description": "Invalid input."},
        fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error."}
    }
)
async def uploadAudio(
    userId: typing.Annotated[str, fastapi.Path(description="The user ID")],
    taskId: typing.Annotated[str, fastapi.Path(description="The task ID")],
    audioFile: typing.Annotated[fastapi.UploadFile, fastapi.File(media_type="audio/mpeg")],
    privacy: typing.Annotated[str, fastapi.Query(description="Privacy level (public/private)")] = "public"
) -> fastapi.responses.JSONResponse:
    """Upload an export audio file to storage."""
    LOGGER.info(f"[EXPORT][AUDIOS] Uploading audio for userId={userId}, taskId={taskId}, privacy={privacy}")
    
    path = await assets_service.submitExportAudio(
        audioFile=audioFile,
        userID=userId,
        taskID=taskId,
        privacy=privacy
    )
    
    return fastapi.responses.JSONResponse(
        status_code=fastapi.status.HTTP_201_CREATED,
        content={
            "message": "Audio file uploaded successfully.",
            "path": path,
            "fileName": "audio.mp3",
            "contentType": audioFile.content_type,
            "privacy": privacy
        }
    )