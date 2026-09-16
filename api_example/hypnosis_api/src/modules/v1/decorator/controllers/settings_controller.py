import typing
import fastapi
from hypnosis_schemas.settings import decorator as hypnosis_decorator_settings
from hypnosis_utils.logger import getLogger
from ..services import settings_service

LOGGER = getLogger("v1.decorator.controllers.settings")

ROUTER = fastapi.APIRouter(
    prefix="/settings",
    tags=["settings"],
)


@ROUTER.get(
    "/byUserLevel/{userLevel}",
    responses={
        fastapi.status.HTTP_200_OK: {"model": hypnosis_decorator_settings.Settings},
        fastapi.status.HTTP_204_NO_CONTENT: {"description": "No settings found"},
        fastapi.status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "Invalid user level"},
        fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error"}
    }
)
async def getSettingsByUserLevel(
    userLevel: typing.Annotated[int, fastapi.Path()],
    language: typing.Annotated[typing.Optional[str], fastapi.Query()] = "es"
) -> hypnosis_decorator_settings.Settings:
    LOGGER.info(f"[DECORATOR] Fetching settings for user level: {userLevel} and language: {language}")
    return await settings_service.getSettingsByUserLevel(userLevel, language)



@ROUTER.get(
    "/all",
    responses={
        fastapi.status.HTTP_200_OK: {"model": typing.List[hypnosis_decorator_settings.Settings]},
        fastapi.status.HTTP_204_NO_CONTENT: {"description": "No settings found"},
        fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error"}
    }
)
async def getAllSettings() -> typing.Iterable[hypnosis_decorator_settings.Settings]:
    LOGGER.info("[DECORATOR] Fetching all settings...")
    return await settings_service.getAllSettings()

@ROUTER.put(
    "/create",
    responses={
        fastapi.status.HTTP_201_CREATED: {"model": hypnosis_decorator_settings.Settings},
        fastapi.status.HTTP_404_NOT_FOUND: {"description": "Settings not found"},
        fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error"}
    }
)
async def createSettings(
    settings: typing.Annotated[hypnosis_decorator_settings.Settings, fastapi.Body()]
) -> fastapi.responses.JSONResponse:
    LOGGER.info(f"[DECORATOR] Creating settings for user level: {settings.userLevel}")
    
    await settings_service.createSettings(settings)

    return fastapi.responses.JSONResponse(status_code=fastapi.status.HTTP_201_CREATED, content=settings.model_dump(mode="json", by_alias=True, round_trip=True))
