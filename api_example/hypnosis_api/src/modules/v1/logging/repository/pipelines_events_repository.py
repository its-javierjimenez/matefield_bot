import typing
import pymongo
import pymongo.errors
import logging
import anyio
import pydantic_mongo
import pydantic_mongo.errors
import tenacity
from src.config import ENVIRONMENT_SETTINGS
from src.modules.v1.shared.connections.databases import mongo as mongo_connections
from ..schemas.logging import logging_schema

LOGGER = logging.getLogger("uvicorn").getChild("v1.logging.repository.settings")


class PipelineEventsRepository(
    pydantic_mongo.AsyncAbstractRepository[
        logging_schema.LoggingSchema
    ]
):
    class Meta:
        collection_name = ENVIRONMENT_SETTINGS.TASK_LOGGING_SETTINGS.LOGGING_PIPELINE_EVENTS_COLLECTION


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
    async def getEvents(
        self,
        query : dict = {}
    ) -> typing.Iterable[logging_schema.LoggingSchema]:

        LOGGER.info("[LOGGING][EVENTS][REPOSITORY] Fetching logging events")
        return await self.find_by_with_output_type(
            output_type=logging_schema.LoggingSchema,
            query=query,
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
    async def aggregateEventsByUser(
        self,
        userEmail: str,
        fromDate: int,
        toDate: int,
    ) -> dict:
        """Aggregate pipeline to count events per eventType for a given user in a time range.

        Matches on `userData.userId` or `userEmail` and groups by `eventType`.
        Returns a mapping { eventType: count }.
        """
        LOGGER.info(
            "[LOGGING][EVENTS][REPOSITORY] Aggregating events for user %s between %s and %s",
            userEmail,
            fromDate,
            toDate,
        )

        # Build aggregation pipeline (userEmail)
        pipeline = [
            {
                "$match": {
                    "timestamp": {"$gte": fromDate, "$lte": toDate},
                    "userEmail": userEmail
                }
            },
            {"$group": {"_id": "$eventType", "count": {"$sum": 1}}},
            {"$group": {"_id": None, "events": {"$push": {"k": "$_id", "v": "$count"}}}},
            {"$replaceRoot": {"newRoot": {"$arrayToObject": "$events"}}},
        ]

        collection = self.get_collection()
        cursor = await collection.aggregate(pipeline)
        docs = await cursor.to_list(length=None)

        # If aggregation returns an empty list, return an empty dict
        if not docs:
            return {}

        # The pipeline returns a single document which is the object mapping
        return docs[0]

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
    async def createEvent(
        self,
        event: logging_schema.LoggingSchema
    ) -> bool:

        LOGGER.info("[LOGGING][EVENTS][REPOSITORY] Creating logging event")
        result = await self.save(
            event
        )

        LOGGER.info(f"[LOGGING][EVENTS][REPOSITORY] Logging event created for pipeline task {event.audioRequestID}")

        return result.acknowledged

PIPELINE_EVENTS_REPOSITORY = PipelineEventsRepository(
    mongo_connections.MONGO_CLIENT[ENVIRONMENT_SETTINGS.TASK_LOGGING_SETTINGS.LOGGING_DATABASE_NAME]
)