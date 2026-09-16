import typing
import fastapi
from hypnosis_schemas.settings import moderator as hypnosis_moderator_settings
from hypnosis_utils.logger import getLogger
from ..services import settings_service

LOGGER = getLogger("v1.moderator.controllers.settings")

ROUTER = fastapi.APIRouter(
    prefix="/settings",
    tags=["settings"],
)


@ROUTER.get(
    "",
    responses={
        fastapi.status.HTTP_200_OK: {"model": hypnosis_moderator_settings.Settings},
        fastapi.status.HTTP_204_NO_CONTENT: {"description": "No settings found"},
        fastapi.status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "Invalid parameters"},
        fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error"}
    }
)
async def getSettings(
    language: typing.Annotated[typing.Optional[str], fastapi.Query()] = "es"
) -> hypnosis_moderator_settings.Settings:
    LOGGER.info(f"[MODERATOR] Fetching settings for language: {language}")
    return await settings_service.getSettings(language)



@ROUTER.get(
    "/all",
    responses={
        fastapi.status.HTTP_200_OK: {"model": typing.List[hypnosis_moderator_settings.Settings]},
        fastapi.status.HTTP_204_NO_CONTENT: {"description": "No settings found"},
        fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error"}
    }
)
async def getAllSettings() -> typing.Iterable[hypnosis_moderator_settings.Settings]:
    LOGGER.info("[MODERATOR] Fetching all settings...")
    return await settings_service.getAllSettings()


@ROUTER.put(
    "/create",
    responses={
        fastapi.status.HTTP_201_CREATED: {"model": hypnosis_moderator_settings.Settings},
        fastapi.status.HTTP_404_NOT_FOUND: {"description": "Settings not found"},
        fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error"}
    }
)
async def createSettings(
    settings: typing.Annotated[hypnosis_moderator_settings.Settings, fastapi.Body(media_type="application/json")]
) -> hypnosis_moderator_settings.Settings:
    LOGGER.info(f"[MODERATOR] Creating settings: {settings}")
    return await settings_service.createSettings(settings)
