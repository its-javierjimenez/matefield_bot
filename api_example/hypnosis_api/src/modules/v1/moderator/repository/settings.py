import typing
import pymongo
import pymongo.errors
import pydantic
import logging
import anyio
import pydantic_mongo
import pydantic_mongo.errors
import tenacity
from hypnosis_schemas.settings import moderator as hypnosis_moderator_settings
from hypnosis_utils.logger import getLogger
from src.config import ENVIRONMENT_SETTINGS
from src.modules.v1.shared.connections.databases import mongo as mongo_connections

LOGGER = getLogger("v1.moderator.repository.settings")

class ModeratorSettingsMongo(
   hypnosis_moderator_settings.Settings,
):
    model_config = pydantic.ConfigDict(
        extra="allow",
        serialize_by_alias=True,
        validate_by_alias=True,
        validate_by_name=True,
    )
    
    id : typing.Optional[pydantic_mongo.PydanticObjectId] = None

class ModeratorRepository(
    pydantic_mongo.AsyncAbstractRepository[
       ModeratorSettingsMongo
    ]
):
    class Meta:
        collection_name = ENVIRONMENT_SETTINGS.MODERATOR_SETTINGS.MODERATOR_SETTINGS_COLLECTION


    @tenacity.retry(
        sleep=anyio.sleep,
        stop=tenacity.stop_after_attempt(3),
        retry=tenacity.retry_if_exception_type(
            (pydantic_mongo.errors.PydanticMongoError , pymongo.errors.PyMongoError)
        ),
        wait=tenacity.wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
        before_sleep=tenacity.before_sleep_log(LOGGER, logging.WARNING)
    )
    async def getSettings(
        self,
        query : dict = {}
    ) -> typing.Iterable[hypnosis_moderator_settings.Settings]:
        
        LOGGER.info(f"[MODERATOR] Fetching settings with query: {query}")

        settings = await self.find_by(
            query=query
        )

        return [
            hypnosis_moderator_settings.Settings.model_validate(setting.model_dump(mode="json", by_alias=True , round_trip=True))
            for setting in settings
        ]
    
    @tenacity.retry(
        sleep=anyio.sleep,
        stop=tenacity.stop_after_attempt(3),
        retry=tenacity.retry_if_exception_type(
            (pydantic_mongo.errors.PydanticMongoError , pymongo.errors.PyMongoError)
        ),
        wait=tenacity.wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
        before_sleep=tenacity.before_sleep_log(LOGGER, logging.WARNING)
    )
    async def createSettings(
        self,
        settings: hypnosis_moderator_settings.Settings
    ) -> hypnosis_moderator_settings.Settings:
        
        LOGGER.info(f"[MODERATOR] Creating settings: {settings}")

        await self.save(
            model=ModeratorSettingsMongo.model_validate(settings.model_dump(mode="json", by_alias=True , round_trip=True))
        )

        return settings


MODERATOR_REPOSITORY_INSTANCE = ModeratorRepository(
    database=mongo_connections.MONGO_CLIENT.get_database(
        ENVIRONMENT_SETTINGS.MODERATOR_SETTINGS.MODERATOR_SETTINGS_DATABASE
    )
)
