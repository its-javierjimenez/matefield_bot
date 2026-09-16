import typing
import pymongo
import pymongo.errors
import pydantic
import logging
import anyio
import pydantic_mongo
import pydantic_mongo.errors
import tenacity
from hypnosis_schemas.settings import decorator as hypnosis_decorator_settings
from hypnosis_utils.logger import getLogger
from src.config import ENVIRONMENT_SETTINGS
from src.modules.v1.shared.connections.databases import mongo as mongo_connections

LOGGER = getLogger("v1.decorator.repository.settings")

class DecoratorSettingsMongo(
   hypnosis_decorator_settings.Settings,
):
    model_config = pydantic.ConfigDict(
        extra="allow",
        serialize_by_alias=True,
        validate_by_alias=True,
        validate_by_name=True,
    )
    
    id : typing.Optional[pydantic_mongo.PydanticObjectId] = None

class DecoratorRepository(
    pydantic_mongo.AsyncAbstractRepository[
       DecoratorSettingsMongo
    ]
):
    class Meta:
        collection_name = ENVIRONMENT_SETTINGS.DECORATOR_SETTINGS.DECORATOR_SETTINGS_COLLECTION


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
    ) -> typing.Iterable[hypnosis_decorator_settings.Settings]:

        LOGGER.info(f"[DECORATOR] Fetching DECORATOR settings with query: {query}")
        return await self.find_by_with_output_type(
            output_type=hypnosis_decorator_settings.Settings,
            query=query,
            projection={"_id" : 0}
        )

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
        settings: hypnosis_decorator_settings.Settings
    ) -> bool:

        LOGGER.info("[DECORATOR] Creating DECORATOR settings")
        settingsForMongo = DecoratorSettingsMongo(**settings.model_dump(mode="json" , round_trip=True))
        result = await self.save(
            settingsForMongo,
        )

        return result

DECORATOR_REPOSITORY_INSTANCE = DecoratorRepository(
    mongo_connections.MONGO_CLIENT[ENVIRONMENT_SETTINGS.DECORATOR_SETTINGS.DECORATOR_SETTINGS_DATABASE]
)