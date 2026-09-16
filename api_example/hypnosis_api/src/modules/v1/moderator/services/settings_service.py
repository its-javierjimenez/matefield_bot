import aiocache
import typing
import fastapi
import aiocache.serializers
from hypnosis_schemas.settings import moderator as hypnosis_moderator_settings
from hypnosis_utils.logger import getLogger
from ..repository import settings as settings_repository

LOGGER = getLogger("v1.moderator.services.settings")



@aiocache.cached_stampede(
    cache=aiocache.SimpleMemoryCache,
    lease=2, # seconds to lock the call to avoid stampede
    ttl=60, # seconds to cache the result
    namespace="hypnosis-moderator",
    serializer=aiocache.serializers.NullSerializer(), # We want to save the pydantic model as is
    noself=False,
)
async def getSettingsFromDatabase(language: str = "es") -> hypnosis_moderator_settings.Settings:

    LOGGER.info(f"[MODERATOR] Fetching settings for language: {language} from the database...")

    defaultSettings = await settings_repository.MODERATOR_REPOSITORY_INSTANCE.getSettings(
        query={"language": language}
    )

    if not defaultSettings:
        LOGGER.warning("[MODERATOR] No default settings found.")
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_204_NO_CONTENT,
            detail="No default settings found for moderator."
        )
    
    if len(defaultSettings) > 1:
        LOGGER.warning(f"[MODERATOR] More than one default settings found (len {len(defaultSettings)}), returning the first one.")

    toReturn = defaultSettings[0]

    return toReturn



@aiocache.cached_stampede(
    cache=aiocache.SimpleMemoryCache,
    lease=2, # seconds to lock the call to avoid stampede
    ttl=60, # seconds to cache the result
    namespace="hypnosis-moderator",
    serializer=aiocache.serializers.NullSerializer(), # We want to save the pydantic model as is
    noself=False,
)
async def getAllSettings() -> typing.Iterable[hypnosis_moderator_settings.Settings]:
    LOGGER.info("[MODERATOR] Fetching all settings from the database...")
    return await settings_repository.MODERATOR_REPOSITORY_INSTANCE.getSettings()



async def getSettings(language: str = "es") -> hypnosis_moderator_settings.Settings:
    return await getSettingsFromDatabase(language)



async def createSettings(settings: hypnosis_moderator_settings.Settings) -> hypnosis_moderator_settings.Settings:
    return await settings_repository.MODERATOR_REPOSITORY_INSTANCE.createSettings(settings)
