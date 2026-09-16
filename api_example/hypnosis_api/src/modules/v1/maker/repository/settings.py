import typing
import pymongo
import pymongo.errors
import pydantic
import logging
import anyio
import pydantic_mongo
import pydantic_mongo.errors
import tenacity
from hypnosis_utils.logger import getLogger
from src.config import ENVIRONMENT_SETTINGS
from src.modules.v1.shared.connections.databases import mongo as mongo_connections

from hypnosis_schemas.settings.maker import (
    Settings
)

LOGGER = getLogger("v1.maker.repository.settings")

class MakerSettingsMongo(
   Settings,
):
    model_config = pydantic.ConfigDict(
        extra="allow",
        serialize_by_alias=True,
        validate_by_alias=True,
        validate_by_name=True,
    )
    
    id : typing.Optional[pydantic_mongo.PydanticObjectId] = None

class MakerRepository(
    pydantic_mongo.AsyncAbstractRepository[
       MakerSettingsMongo
    ]
):
    class Meta:
        collection_name = ENVIRONMENT_SETTINGS.MAKER_SETTINGS.MAKER_SETTINGS_COLLECTION


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
    ) -> typing.Iterable[Settings]:

        LOGGER.info("[MAKER][SETTINGS][REPOSITORY] Fetching maker settings")
        return await self.find_by_with_output_type(
            output_type=Settings,
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
        settings: Settings
    ) -> bool:

        LOGGER.info("[MAKER][SETTINGS][REPOSITORY] Creating maker settings")
        settingsForMongo = MakerSettingsMongo(**settings.model_dump(mode="json" , round_trip=True , by_alias=True))
        result = await self.save(
            settingsForMongo,
        )

        return result.acknowledged

MAKER_REPOSITORY_INSTANCE = MakerRepository(
    mongo_connections.MONGO_CLIENT[ENVIRONMENT_SETTINGS.MAKER_SETTINGS.MAKER_SETTINGS_DATABASE]
)