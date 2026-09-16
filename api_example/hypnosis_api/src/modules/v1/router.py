import logging
import fastapi
import faststream.rabbit.fastapi as faststream_rabbit
from faststream import Logger as FaststreamLogger

from src.config import ENVIRONMENT_SETTINGS
from src.security import api_key as security_api_key
from .maker import (ROUTER as MAKER_ROUTER , bindQueues as bindMakerQueues)
from .export import (ROUTER as EXPORT_ROUTER, bindQueues as bindExportQueues)
from .decorator import (ROUTER as DECORATOR_ROUTER, bindQueues as bindDecoratorQueues)
from .caronte import ROUTER as CARONTE_ROUTER
from .logging import (ROUTER as LOGGING_ROUTER, bindQueues as bindLoggingQueues)
from .moderator import (ROUTER as MODERATOR_ROUTER, bindQueues as bindModeratorQueues)

LOGGER: logging.Logger = FaststreamLogger("v1.router")

ROUTER = faststream_rabbit.RabbitRouter(
    url=ENVIRONMENT_SETTINGS.RABBIT_SETTINGS.RABBIT_URL,
    tags=["v1"],
    prefix="/v1",
    timeout=15,
    graceful_timeout=60,
    reconnect_interval=5,
    fail_fast=False,
    include_in_schema=True,
    dependencies=[fastapi.Depends(security_api_key.apiKeyScheme)],
)

async def onStartup(*args, **kwargs):
    global ROUTER
    LOGGER.info("[V1] Starting RabbitMQ connection...")
    await bindExportQueues(ROUTER.broker)
    await bindMakerQueues(ROUTER.broker)
    await bindDecoratorQueues(ROUTER.broker)
    await bindLoggingQueues(ROUTER.broker)
    await bindModeratorQueues(ROUTER.broker)
    LOGGER.info("[V1] RabbitMQ connection established and queues bound.")

ROUTER.after_startup(onStartup)

ROUTER.include_router(
    MAKER_ROUTER
)

ROUTER.include_router(
    EXPORT_ROUTER
)

ROUTER.include_router(
    DECORATOR_ROUTER
)

ROUTER.include_router(
    CARONTE_ROUTER
)

ROUTER.include_router(
    LOGGING_ROUTER
)

ROUTER.include_router(
    MODERATOR_ROUTER
)