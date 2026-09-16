import logging
import typing

import anyio
import pydantic_mongo
import pydantic_mongo.errors
import pymongo
import pymongo.errors
import tenacity

from src.config import ENVIRONMENT_SETTINGS
from src.modules.v1.shared.connections.databases import mongo as mongo_connections

from ..schemas.logging import logging_schema

LOGGER = logging.getLogger("uvicorn").getChild("v1.logging.repository.webhooks")


class PipelineEventsWebhooksRepository(
    pydantic_mongo.AsyncAbstractRepository[logging_schema.LoggingWebhookSchema]
):
    class Meta:
        collection_name = ENVIRONMENT_SETTINGS.TASK_LOGGING_SETTINGS.LOGGING_PIPELINE_EVENTS_WEBHOOKS_COLLECTION

    @tenacity.retry(
        sleep=anyio.sleep,
        stop=tenacity.stop_after_attempt(3),
        retry=tenacity.retry_if_exception_type(
            (pydantic_mongo.errors.PydanticMongoError, pymongo.errors.PyMongoError)
        ),
        wait=tenacity.wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
        before_sleep=tenacity.before_sleep_log(LOGGER, logging.WARNING),
    )
    async def createWebhook(
        self,
        webhook: logging_schema.LoggingWebhookSchema,
    ) -> logging_schema.LoggingWebhookSchema:
        LOGGER.info(
            "[LOGGING][WEBHOOKS][REPOSITORY] Registrando webhook para el servicio %s",
            webhook.serviceName,
        )
        result = await self.save(webhook)
        stored = webhook.model_copy()
        stored.id = result.inserted_id
        return stored

    @tenacity.retry(
        sleep=anyio.sleep,
        stop=tenacity.stop_after_attempt(3),
        retry=tenacity.retry_if_exception_type(
            (pydantic_mongo.errors.PydanticMongoError, pymongo.errors.PyMongoError)
        ),
        wait=tenacity.wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
        before_sleep=tenacity.before_sleep_log(LOGGER, logging.WARNING),
    )
    async def listWebhooks(
        self,
        isActive: typing.Optional[bool] = True,
    ) -> typing.Iterable[logging_schema.LoggingWebhookSchema]:
        query: dict[str, typing.Any] = {}
        if isActive is not None:
            query["isActive"] = isActive

        LOGGER.info(
            "[LOGGING][WEBHOOKS][REPOSITORY] Consultando webhooks con query %s",
            query,
        )
        return await self.find_by_with_output_type(
            output_type=logging_schema.LoggingWebhookSchema,
            query=query,
        )


PIPELINE_EVENTS_WEBHOOKS_REPOSITORY_INSTANCE = PipelineEventsWebhooksRepository(
    mongo_connections.MONGO_CLIENT[ENVIRONMENT_SETTINGS.TASK_LOGGING_SETTINGS.LOGGING_DATABASE_NAME]
)
