import faststream.rabbit
import hypnosis_rabbit
from src.config import ENVIRONMENT_SETTINGS


HYPNOSIS_DEAD_LETTER = hypnosis_rabbit.factories.createRabbitQueue(
    queueName=ENVIRONMENT_SETTINGS.RABBIT_SETTINGS.RABBIT_HYPNOSIS_DEAD_LETTER_QUEUE_NAME,
    routingKey=ENVIRONMENT_SETTINGS.RABBIT_SETTINGS.RABBIT_HYPNOSIS_DEAD_LETTER_QUEUE_ROUTING_KEY,
    queueType=faststream.rabbit.QueueType.CLASSIC,
    dlExchange=None,
    dlQueueRoutingKey=None,
    durable=True,
)


SHARED_HYPNOSIS_QUEUES = {
    "dead_letter": HYPNOSIS_DEAD_LETTER,
}