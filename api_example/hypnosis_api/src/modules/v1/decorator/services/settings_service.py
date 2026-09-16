import aiocache
import typing
import fastapi
import aiocache.serializers
from hypnosis_schemas.settings import decorator as hypnosis_decorator_settings
from hypnosis_utils.logger import getLogger
from ..repository import settings as settings_repository

LOGGER = getLogger("v1.decorator.services.settings")



@aiocache.cached_stampede(
    cache=aiocache.SimpleMemoryCache,
    lease=2, # seconds to lock the call to avoid stampede
    ttl=60, # seconds to cache the result
    namespace="hypnosis-decorator",
    serializer=aiocache.serializers.NullSerializer(), # We want to save the pydantic model as is
    noself=False,
)
async def getSettingsByUserlevelFromDatabase(userLevel: int , language: str = "es") -> hypnosis_decorator_settings.Settings:

    LOGGER.info(f"[DECORATOR] Fetching settings for user level: {userLevel} and language: {language} from the database...")

    defaultSettings = await settings_repository.DECORATOR_REPOSITORY_INSTANCE.getSettings(
        query={"userLevel": userLevel, "language": language}
    )

    if not defaultSettings:
        LOGGER.warning("[DECORATOR] No default settings found.")
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_204_NO_CONTENT,
            detail="No default settings found for decorator."
        )
    
    if len(defaultSettings) > 1:
        LOGGER.warning(f"[DECORATOR] More than one default settings found (len {len(defaultSettings)}), returning the first one.")

    toReturn = defaultSettings[0]

    return toReturn



@aiocache.cached_stampede(
    cache=aiocache.SimpleMemoryCache,
    lease=2, # seconds to lock the call to avoid stampede
    ttl=60, # seconds to cache the result
    namespace="hypnosis-decorator",
    serializer=aiocache.serializers.NullSerializer(), # We want to save the pydantic model as is
    noself=False,
    skip_cache_func=lambda r: len(r) < 1 # if len < 1, skip cache
)
async def getAllSettingsFromDatabase() -> typing.Iterable[hypnosis_decorator_settings.Settings]:
    LOGGER.info("[DECORATOR] Fetching all settings from the database...")
    return await settings_repository.DECORATOR_REPOSITORY_INSTANCE.getSettings()


async def createSettings(settings: hypnosis_decorator_settings.Settings) -> bool:
    LOGGER.info(f"[DECORATOR] Creating settings: {settings.userLevel}")
    return await settings_repository.DECORATOR_REPOSITORY_INSTANCE.createSettings(settings)

# ? TYPES

getSettingsByUserLevel = typing.cast(
    typing.Callable[[int, str], typing.Awaitable[hypnosis_decorator_settings.Settings]],
    getSettingsByUserlevelFromDatabase
)

getAllSettings = typing.cast(
    typing.Callable[[], typing.Awaitable[typing.Iterable[hypnosis_decorator_settings.Settings]]],
    getAllSettingsFromDatabase
)