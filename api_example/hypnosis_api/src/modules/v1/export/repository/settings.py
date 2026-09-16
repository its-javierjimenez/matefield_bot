import typing
import pymongo
import pymongo.errors
import pydantic
import logging
import anyio
import pydantic_mongo
import pydantic_mongo.errors
import tenacity
from hypnosis_schemas.settings import export as hypnosis_export_settings
from hypnosis_utils.logger import getLogger
from src.config import ENVIRONMENT_SETTINGS
from src.modules.v1.shared.connections.databases import mongo as mongo_connections

LOGGER = getLogger("v1.export.repository.settings")

class ExportSettingsMongo(
   hypnosis_export_settings.Settings,
):
    model_config = pydantic.ConfigDict(
        extra="allow",
        serialize_by_alias=True,
        validate_by_alias=True,
        validate_by_name=True,
    )
    
    id : typing.Optional[pydantic_mongo.PydanticObjectId] = None

class ExportRepository(
    pydantic_mongo.AsyncAbstractRepository[
       ExportSettingsMongo
    ]
):
    class Meta:
        collection_name = ENVIRONMENT_SETTINGS.EXPORT_SETTINGS.EXPORT_SETTINGS_COLLECTION


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
    ) -> typing.Iterable[hypnosis_export_settings.Settings]:

        LOGGER.info(f"[EXPORT] Fetching EXPORT settings with query: {query}")
        return await self.find_by_with_output_type(
            output_type=hypnosis_export_settings.Settings,
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
        settings: hypnosis_export_settings.Settings
    ) -> bool:

        LOGGER.info("[EXPORT] Creating EXPORT settings")
        settingsForMongo = ExportSettingsMongo(**settings.model_dump(mode="json" , round_trip=True))
        result = await self.save(
            settingsForMongo,
        )

        return result

EXPORT_REPOSITORY_INSTANCE = ExportRepository(
    mongo_connections.MONGO_CLIENT[ENVIRONMENT_SETTINGS.EXPORT_SETTINGS.EXPORT_SETTINGS_DATABASE]
)