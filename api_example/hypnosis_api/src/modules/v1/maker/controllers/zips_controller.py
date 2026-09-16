import typing
import fastapi

from hypnosis_utils.logger import getLogger
from src.modules.v1.shared.services import assets_service



LOGGER = getLogger("v1.maker.controllers.zips")



ROUTER = fastapi.APIRouter(
    prefix="/zips",
    tags=["zips" , "assets"],
)



@ROUTER.head(
    "/{userID}/{taskID}",
    description="Check if a maker zip exists for the given user and task.",
    responses={
        fastapi.status.HTTP_200_OK: {"description": "Zip file exists."},
        fastapi.status.HTTP_404_NOT_FOUND: {"description": "Zip file not found."},
        fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error."}
    }
)
async def checkZipExists(
    userID: typing.Annotated[str, fastapi.Path(description="The user ID")],
    taskID: typing.Annotated[str, fastapi.Path(description="The task ID")],
) -> fastapi.Response:
    """Check if a maker zip file exists in storage."""
    LOGGER.info(f"[MAKER][ZIPS] Checking zip existence for userID={userID}, taskID={taskID}")
    
    await assets_service.checkMakerZipExists(userID=userID, taskID=taskID)
    
    return fastapi.Response(status_code=fastapi.status.HTTP_200_OK)



@ROUTER.get(
    "/{userID}/{taskID}",
    description="Download a maker zip file for the given user and task.",
    response_class=fastapi.responses.StreamingResponse,
    responses={
        fastapi.status.HTTP_200_OK: {
            "content": {"application/zip": {}},
            "description": "Zip file retrieved successfully."
        },
        fastapi.status.HTTP_404_NOT_FOUND: {"description": "Zip file not found."},
        fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error."}
    }
)
async def getZip(
    userID: typing.Annotated[str, fastapi.Path(description="The user ID")],
    taskID: typing.Annotated[str, fastapi.Path(description="The task ID")],
) -> fastapi.responses.StreamingResponse:
    """Download a maker zip file from storage."""
    LOGGER.info(f"[MAKER][ZIPS] Downloading zip for userID={userID}, taskID={taskID}")
    
    zipIter, response = await assets_service.getMakerZip(userID=userID, taskID=taskID)
    
    return fastapi.responses.StreamingResponse(
        content=zipIter,
        status_code=fastapi.status.HTTP_200_OK,
        media_type="application/zip",
        headers={
            "content-type": "application/zip",
            "Content-Disposition": f"attachment; filename={taskID}.zip"
        },
        background=fastapi.BackgroundTasks([response.aclose])
    )



@ROUTER.get(
    "/byPath",
    description="Get the path of a maker zip file for the given user and task.",
    response_class=fastapi.responses.StreamingResponse,
    responses={
        fastapi.status.HTTP_200_OK: {"description": "Zip file path retrieved successfully."},
        fastapi.status.HTTP_404_NOT_FOUND: {"description": "Zip file not found."},
        fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error."}
    }
)
async def getZipByPath(
    zipPath: typing.Annotated[str, fastapi.Body(description="The path of the zip file")],
) -> fastapi.responses.JSONResponse:
    """Get the path of a maker zip file from storage."""
    LOGGER.info(f"[MAKER][ZIPS] Getting zip by path: {zipPath}")
    
    zipIter, response = await assets_service.getAssetFromPath(path=zipPath)

    return fastapi.responses.StreamingResponse(
        content=zipIter,
        status_code=fastapi.status.HTTP_200_OK,
        media_type="application/zip",
        headers={
            "content-type": "application/zip",
            "Content-Disposition": f"attachment; filename={zipPath.split('/')[-1]}"
        },
        background=fastapi.BackgroundTasks([response.aclose])
    )



@ROUTER.put(
    "/{userID}/{taskID}",
    description="Upload a maker zip file for the given user and task.",
    response_class=fastapi.responses.JSONResponse,
    responses={
        fastapi.status.HTTP_201_CREATED: {"description": "Zip file uploaded successfully."},
        fastapi.status.HTTP_400_BAD_REQUEST: {"description": "Invalid input."},
        fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error."}
    }
)
async def uploadZip(
    userID: typing.Annotated[str, fastapi.Path(description="The user ID")],
    taskID: typing.Annotated[str, fastapi.Path(description="The task ID")],
    zipFile: typing.Annotated[fastapi.UploadFile, fastapi.File(media_type="application/zip")],
    privacy: typing.Annotated[str, fastapi.Query(description="Privacy level (public/private)")] = "private"
) -> fastapi.responses.JSONResponse:
    """Upload a maker zip file to storage."""
    LOGGER.info(f"[MAKER][ZIPS] Uploading zip for userID={userID}, taskID={taskID}, privacy={privacy}")
    
    path = await assets_service.submitMakerZip(
        zipFile=zipFile,
        userID=userID,
        taskID=taskID,
        privacy=privacy
    )
    
    return fastapi.responses.JSONResponse(
        status_code=fastapi.status.HTTP_201_CREATED,
        content={
            "message": "Zip file uploaded successfully.",
            "path": path,
            "fileName": f"{taskID}.zip",
            "contentType": zipFile.content_type,
            "privacy": privacy
        }
    )