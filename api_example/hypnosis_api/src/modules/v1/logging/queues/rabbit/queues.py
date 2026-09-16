import logging
import faststream.rabbit
from faststream import Logger as FaststreamLogger
from src.config import ENVIRONMENT_SETTINGS
from src.modules.v1.shared.queues.rabbit import (
    exchanges as shared_rabbit_exchanges
)

LOGGER : logging.Logger = FaststreamLogger("v1.logging.queues.rabbit.queues")

HYPNOSIS_LOGGING_QUEUE = faststream.rabbit.RabbitQueue(
    name=ENVIRONMENT_SETTINGS.RABBIT_SETTINGS.RABBIT_HYPNOSIS_LOGGING_QUEUE_NAME,
    durable=True,
    robust=True,
    auto_delete=False,
    declare=True,
    routing_key=ENVIRONMENT_SETTINGS.RABBIT_SETTINGS.RABBIT_HYPNOSIS_LOGGING_QUEUE_ROUTING_KEY
)

LOGGING_QUEUES = {
    "logging_tasks": HYPNOSIS_LOGGING_QUEUE,
}

async def bindQueues(broker: faststream.rabbit.RabbitBroker) -> None:
    """
    Bind the RabbitMQ queues to the exchange.
    
    This function binds the task queue, retry queue, and priority queue to the HYPNOSIS exchange.
    It also binds the export task queue to the EXPORT exchange.
    
    Returns:
        None
    """
    await broker.connect()
    LOGGER.info("[LOGGING] Binding queues to exchanges...")

    declaredHypnosisExchange = await broker.declare_exchange(shared_rabbit_exchanges.HYPNOSIS_EXCHANGE)
    LOGGER.info(f"[LOGGING] Declared exchange {declaredHypnosisExchange.name} with type {declaredHypnosisExchange._type}")


    for queue in LOGGING_QUEUES.values():
        q = await broker.declare_queue(queue)
        LOGGER.info(f"[LOGGING] Declared queue {queue.name} with routing key {queue.routing_key}")
        await q.bind(declaredHypnosisExchange, routing_key=queue.routing_key)
        LOGGER.info(f"[LOGGING] Binded queue {queue.name} to exchange {declaredHypnosisExchange.name} with routing key {queue.routing_key}")