import typing

import fastapi

from hypnosis_utils.logger import getLogger
from src.modules.v1.shared.services import assets_service



LOGGER = getLogger("v1.export.controllers.templates")



ROUTER = fastapi.APIRouter(
    prefix="/templates",
    tags=["templates", "assets"],
)

@ROUTER.head(
    "/byName/{templateName}",
    responses={
        fastapi.status.HTTP_200_OK: {"description": "Template exists"},
        fastapi.status.HTTP_204_NO_CONTENT: {"description": "No template found for the specified name"},
        fastapi.status.HTTP_400_BAD_REQUEST: {"description": "Invalid template name"},
        fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error"},
        fastapi.status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "Unprocessable entity"}
    }
)
async def checkTemplateByName(
    templateName: typing.Annotated[str, fastapi.Path()],
) -> None:
    LOGGER.info(f"[EXPORT] Checking existence of template audio for name: {templateName}")

    if not await assets_service.checkExportTemplateExists(
        filename=templateName,
    ):
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_204_NO_CONTENT,
            detail=f"Template '{templateName}' not found"
        )

@ROUTER.get(
    "/byName/{templateName}",
    response_class=fastapi.responses.StreamingResponse,
    responses={
        fastapi.status.HTTP_200_OK: {
            "content": {"audio/mpeg": {}},
            "description": "Template audio retrieved successfully"
        },
        fastapi.status.HTTP_204_NO_CONTENT: {"description": "No template found for the specified name"},
        fastapi.status.HTTP_400_BAD_REQUEST: {"description": "Invalid template name"},
        fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error"},
        fastapi.status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "Unprocessable entity"}
    }
)
async def getTemplateByName(
    templateName: typing.Annotated[str, fastapi.Path()],
) -> fastapi.responses.StreamingResponse:
    LOGGER.info(f"[EXPORT] Fetching template audio for name: {templateName}")

    if not await assets_service.checkExportTemplateExists(
        filename=templateName,
    ):
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_204_NO_CONTENT,
            detail=f"Template '{templateName}' not found"
        )

    templateIter = await assets_service.getExportTemplate(
        filename=templateName,
    )

    return fastapi.responses.StreamingResponse(
        content=templateIter[0], status_code=fastapi.status.HTTP_200_OK, media_type="audio/mpeg",
        headers={"content-type": "audio/mpeg" , "Content-Disposition": f"attachment; filename={templateName}"},
        background=fastapi.BackgroundTasks([templateIter[1].aclose])
    )


@ROUTER.head(
    "/byUserLevel/{userLevel}",
    responses={
        fastapi.status.HTTP_200_OK: {"description": "Template exists"},
        fastapi.status.HTTP_204_NO_CONTENT: {"description": "No template found for the specified user level"},
        fastapi.status.HTTP_400_BAD_REQUEST: {"description": "Invalid user level"},
        fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error"},
        fastapi.status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "Unprocessable entity"}
    }
)
async def checkTemplatesByUserLevel(
    userLevel: typing.Annotated[str, fastapi.Path()],
    language: typing.Annotated[str, fastapi.Query()] = "es"
) -> None:
    LOGGER.info(f"[EXPORT] Checking existence of template audio for user level: {userLevel} and language: {language}")

    if not await assets_service.checkExportTemplateExists(
        filename=f"template_nivel_{userLevel}_lang_{language}.mp3",
    ):
        LOGGER.info(f"[EXPORT] Template 'template_nivel_{userLevel}_lang_{language}.mp3' does not exist")
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_204_NO_CONTENT,
            detail=f"Template 'template_nivel_{userLevel}_lang_{language}.mp3' not found"
        )

@ROUTER.get(
    "/byUserLevel/{userLevel}",
    response_class=fastapi.responses.StreamingResponse,
    responses={
        fastapi.status.HTTP_200_OK: {
            "content": {"audio/mpeg": {}},
            "description": "Template audio retrieved successfully"
        },
        fastapi.status.HTTP_204_NO_CONTENT: {"description": "No template found for the specified user level"},
        fastapi.status.HTTP_400_BAD_REQUEST: {"description": "Invalid user level"},
        fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error"},
        fastapi.status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "Unprocessable entity"}
    }
)
async def getTemplatesByUserLevel(
    userLevel: typing.Annotated[str, fastapi.Path()],
    language: typing.Annotated[str, fastapi.Query()] = "es"
) -> fastapi.responses.StreamingResponse:
    LOGGER.info(f"[EXPORT] Fetching template audio for user level: {userLevel} and language: {language}")

    if not await assets_service.checkExportTemplateExists(
        filename=f"template_nivel_{userLevel}_lang_{language}.mp3",
    ):
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_204_NO_CONTENT,
            detail=f"Template 'template_nivel_{userLevel}_lang_{language}.mp3' not found"
        )

    templateIter = await assets_service.getExportTemplate(
        filename=f"template_nivel_{userLevel}_lang_{language}.mp3",
    )

    return fastapi.responses.StreamingResponse(
        content=templateIter[0], status_code=fastapi.status.HTTP_200_OK, media_type="audio/mpeg",
        headers={"content-type": "audio/mpeg" , "Content-Disposition": f"attachment; filename=template_nivel_{userLevel}.mp3"},
        background=fastapi.BackgroundTasks([templateIter[1].aclose])
    )



@ROUTER.put(
    "/create/{userLevel}",
    response_class=fastapi.responses.JSONResponse,
    responses={
        fastapi.status.HTTP_201_CREATED: {"description": "Template created successfully"},
        fastapi.status.HTTP_400_BAD_REQUEST: {"description": "Invalid request"},
        fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error"},
        fastapi.status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "Unprocessable entity"}
    }
)
async def createTemplate(
    userLevel: typing.Annotated[str, fastapi.Path()],
    templateFile: typing.Annotated[fastapi.UploadFile, fastapi.File(media_type="audio/mpeg")],
    language: typing.Annotated[str, fastapi.Query()] = "es"
) -> fastapi.responses.JSONResponse:
    LOGGER.info(f"[EXPORT] Creating template for user level: {userLevel}")

    await assets_service.submitExportTemplate(
        filename=f"template_nivel_{userLevel}_lang_{language}.mp3",
        file=templateFile,
        privacy="private"
    )

    return fastapi.responses.JSONResponse(
        content={"message": "Template created successfully", "filename": f"template_nivel_{userLevel}_lang_{language}.mp3"},
        status_code=fastapi.status.HTTP_201_CREATED
    )