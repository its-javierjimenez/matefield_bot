import faststream.rabbit
import hypnosis_rabbit
from src.config import ENVIRONMENT_SETTINGS

HYPNOSIS_EXCHANGE = hypnosis_rabbit.factories.createRabbitExchange(
    exchangeName=ENVIRONMENT_SETTINGS.RABBIT_SETTINGS.RABBIT_HYPNOSIS_EXCHANGE_NAME,
    exchangeType=faststream.rabbit.ExchangeType.TOPIC,
    durable=True,
)