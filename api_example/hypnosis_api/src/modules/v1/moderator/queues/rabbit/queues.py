import faststream.rabbit
from hypnosis_utils.logger import getLogger
import hypnosis_rabbit

from src.config import ENVIRONMENT_SETTINGS
from src.modules.v1.shared.queues.rabbit import (
    queues as shared_rabbit_queues,
    exchanges as shared_rabbit_exchanges
)

LOGGER = getLogger("v1.moderator.queues.rabbit.queues")

HYPNOSIS_MODERATOR_NORMAL_TASKS = hypnosis_rabbit.factories.createRabbitQueue(
    queueName=ENVIRONMENT_SETTINGS.RABBIT_SETTINGS.RABBIT_HYPNOSIS_MODERATOR_NORMAL_TASKS_QUEUE_NAME,
    routingKey=ENVIRONMENT_SETTINGS.RABBIT_SETTINGS.RABBIT_HYPNOSIS_MODERATOR_NORMAL_TASKS_QUEUE_ROUTING_KEY,
    queueType=faststream.rabbit.QueueType.CLASSIC,
    dlExchange=shared_rabbit_exchanges.HYPNOSIS_EXCHANGE,
    dlQueueRoutingKey=shared_rabbit_queues.HYPNOSIS_DEAD_LETTER.routing_key,
    durable=True,
)

HYPNOSIS_MODERATOR_PRIORITY_TASKS = hypnosis_rabbit.factories.createRabbitQueue(
    queueName=ENVIRONMENT_SETTINGS.RABBIT_SETTINGS.RABBIT_HYPNOSIS_MODERATOR_PRIORITY_TASKS_QUEUE_NAME,
    routingKey=ENVIRONMENT_SETTINGS.RABBIT_SETTINGS.RABBIT_HYPNOSIS_MODERATOR_PRIORITY_TASKS_QUEUE_ROUTING_KEY,
    queueType=faststream.rabbit.QueueType.CLASSIC,
    dlExchange=shared_rabbit_exchanges.HYPNOSIS_EXCHANGE,
    dlQueueRoutingKey=shared_rabbit_queues.HYPNOSIS_DEAD_LETTER.routing_key,
    durable=True,
)

MODERATOR_QUEUES = {
    "tasks_normal": HYPNOSIS_MODERATOR_NORMAL_TASKS,
    "tasks_priority": HYPNOSIS_MODERATOR_PRIORITY_TASKS,
    "dead_letter": shared_rabbit_queues.HYPNOSIS_DEAD_LETTER
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
    LOGGER.info("[MODERATOR] Binding queues to exchanges...")

    declaredHypnosisExchange = await broker.declare_exchange(shared_rabbit_exchanges.HYPNOSIS_EXCHANGE)
    LOGGER.info(f"[MODERATOR] Declared exchange {declaredHypnosisExchange.name} with type {declaredHypnosisExchange._type}")


    for queue in MODERATOR_QUEUES.values():
        q = await broker.declare_queue(queue)
        LOGGER.info(f"[MODERATOR] Declared queue {queue.name} with routing key {queue.routing_key}")
        await q.bind(declaredHypnosisExchange, routing_key=queue.routing_key)
        LOGGER.info(f"[MODERATOR] Binded queue {queue.name} to exchange {declaredHypnosisExchange.name} with routing key {queue.routing_key}")