import pydantic
from hypnosis_config import BaseSettings


class RabbitSettings(BaseSettings):

    RABBIT_URL: str = pydantic.Field(
        default="amqp://guest:guest@localhost:5672/",
        description="The RabbitMQ URL"
    )

    RABBIT_MANAGEMENT_URL: str = pydantic.Field(
        default="http://localhost:15672/api",
        description="Base URL for RabbitMQ management API"
    )

    RABBIT_MANAGEMENT_USERNAME: str = pydantic.Field(
        default="guest",
        description="Username for RabbitMQ management API"
    )

    RABBIT_MANAGEMENT_PASSWORD: str = pydantic.Field(
        default="guest",
        description="Password for RabbitMQ management API"
    )

    RABBIT_MANAGEMENT_VHOST: str = pydantic.Field(
        default="/",
        description="RabbitMQ virtual host used in management API calls"
    )

    RABBIT_MANAGEMENT_TIMEOUT_SECONDS: int = pydantic.Field(
        default=10,
        description="Timeout in seconds for RabbitMQ management API requests"
    )
    
    RABBIT_HYPNOSIS_EXCHANGE_NAME: str = pydantic.Field(
        default="hypnosis-exchange",
        description="The name of the RabbitMQ exchange"
    )

    #### MAKER

    ####### NORMAL

    ############## TASKS

    RABBIT_HYPNOSIS_MAKER_NORMAL_TASKS_QUEUE_NAME: str = pydantic.Field(
        ...,
        description="The name of the RabbitMQ maker queue"
    )

    RABBIT_HYPNOSIS_MAKER_NORMAL_TASKS_QUEUE_ROUTING_KEY: str = pydantic.Field(
        ...,
        description="The routing key for the RabbitMQ maker queue"
    )

    ############## RETRY

    RABBIT_HYPNOSIS_MAKER_NORMAL_RETRY_TASKS_QUEUE_NAME: str = pydantic.Field(
        ...,
        description="The name of the RabbitMQ normal retry maker queue"
    )

    RABBIT_HYPNOSIS_MAKER_NORMAL_RETRY_TASKS_QUEUE_ROUTING_KEY: str = pydantic.Field(
        ...,
        description="The routing key for the RabbitMQ normal retry maker queue"
    )


    ####### PRIORITY

    ########## TASKS

    RABBIT_HYPNOSIS_MAKER_PRIORITY_TASKS_QUEUE_NAME: str = pydantic.Field(
        ...,
        description="The name of the RabbitMQ priority maker queue"
    )

    RABBIT_HYPNOSIS_MAKER_PRIORITY_TASKS_QUEUE_ROUTING_KEY: str = pydantic.Field(
        ...,
        description="The routing key for the RabbitMQ priority maker queue"
    )

    ########## RETRY

    RABBIT_HYPNOSIS_MAKER_PRIORITY_RETRY_TASKS_QUEUE_NAME: str = pydantic.Field(
        ...,
        description="The name of the RabbitMQ priority retry queue"
    )

    RABBIT_HYPNOSIS_MAKER_PRIORITY_RETRY_TASKS_QUEUE_ROUTING_KEY: str = pydantic.Field(
        ...,
        description="The routing key for the RabbitMQ priority retry queue"
    )

    #### EXPORT

    ####### NORMAL

    ########## TASKS

    RABBIT_HYPNOSIS_EXPORT_NORMAL_TASKS_QUEUE_NAME: str = pydantic.Field(
        ...,
        description="The name of the RabbitMQ export tasks queue"
    )

    RABBIT_HYPNOSIS_EXPORT_NORMAL_TASKS_QUEUE_ROUTING_KEY: str = pydantic.Field(
        ...,
        description="The routing key for the RabbitMQ export tasks queue"
    )

    ########## RETRY

    RABBIT_HYPNOSIS_EXPORT_NORMAL_RETRY_TASKS_QUEUE_NAME: str = pydantic.Field(
        ...,
        description="The name of the RabbitMQ export retry tasks queue"
    )

    RABBIT_HYPNOSIS_EXPORT_NORMAL_RETRY_TASKS_QUEUE_ROUTING_KEY: str = pydantic.Field(
        ...,
        description="The routing key for the RabbitMQ export retry tasks queue"
    )

    ####### PRIORITY

    ########## TASKS

    RABBIT_HYPNOSIS_EXPORT_PRIORITY_TASKS_QUEUE_NAME: str = pydantic.Field(
        ...,
        description="The name of the RabbitMQ export priority tasks queue"
    )

    RABBIT_HYPNOSIS_EXPORT_PRIORITY_TASKS_QUEUE_ROUTING_KEY: str = pydantic.Field(
        ...,
        description="The routing key for the RabbitMQ export priority tasks queue"
    )

    ########### RETRY

    RABBIT_HYPNOSIS_EXPORT_PRIORITY_RETRY_TASKS_QUEUE_NAME: str = pydantic.Field(
        ...,
        description="The name of the RabbitMQ export priority retry tasks queue"
    )

    RABBIT_HYPNOSIS_EXPORT_PRIORITY_RETRY_TASKS_QUEUE_ROUTING_KEY: str = pydantic.Field(
        ...,
        description="The routing key for the RabbitMQ export priority retry tasks queue"
    )


    #### DECORATOR

    ####### NORMAL

    ########## TASKS

    RABBIT_HYPNOSIS_DECORATOR_NORMAL_TASKS_QUEUE_NAME: str = pydantic.Field(
        ...,
        description="The name of the RabbitMQ decorator tasks queue"
    )

    RABBIT_HYPNOSIS_DECORATOR_NORMAL_TASKS_QUEUE_ROUTING_KEY: str = pydantic.Field(
        ...,
        description="The routing key for the RabbitMQ decorator tasks queue"
    )

    ########## RETRY

    RABBIT_HYPNOSIS_DECORATOR_NORMAL_RETRY_TASKS_QUEUE_NAME: str = pydantic.Field(
        ...,
        description="The name of the RabbitMQ decorator normal retry tasks queue"
    )

    RABBIT_HYPNOSIS_DECORATOR_NORMAL_RETRY_TASKS_QUEUE_ROUTING_KEY: str = pydantic.Field(
        ...,
        description="The routing key for the RabbitMQ decorator normal retry tasks queue"
    )

    ####### PRIORITY

    ########## TASKS

    RABBIT_HYPNOSIS_DECORATOR_PRIORITY_TASKS_QUEUE_NAME: str = pydantic.Field(
        ...,
        description="The name of the RabbitMQ decorator priority tasks queue"
    )


    RABBIT_HYPNOSIS_DECORATOR_PRIORITY_TASKS_QUEUE_ROUTING_KEY: str = pydantic.Field(
        ...,
        description="The routing key for the RabbitMQ decorator priority tasks queue"
    )

    ########## RETRY

    RABBIT_HYPNOSIS_DECORATOR_PRIORITY_RETRY_TASKS_QUEUE_NAME: str = pydantic.Field(
        ...,
        description="The name of the RabbitMQ decorator priority retry tasks queue"
    )

    RABBIT_HYPNOSIS_DECORATOR_PRIORITY_RETRY_TASKS_QUEUE_ROUTING_KEY: str = pydantic.Field(
        ...,
        description="The routing key for the RabbitMQ decorator priority retry tasks queue"
    )

    #### MODERATOR

    ####### NORMAL

    ############## TASKS

    RABBIT_HYPNOSIS_MODERATOR_NORMAL_TASKS_QUEUE_NAME: str = pydantic.Field(
        ...,
        description="The name of the RabbitMQ moderator queue"
    )

    RABBIT_HYPNOSIS_MODERATOR_NORMAL_TASKS_QUEUE_ROUTING_KEY: str = pydantic.Field(
        ...,
        description="The routing key for the RabbitMQ moderator queue"
    )

    ####### PRIORITY

    ########## TASKS

    RABBIT_HYPNOSIS_MODERATOR_PRIORITY_TASKS_QUEUE_NAME: str = pydantic.Field(
        ...,
        description="The name of the RabbitMQ priority moderator queue"
    )

    RABBIT_HYPNOSIS_MODERATOR_PRIORITY_TASKS_QUEUE_ROUTING_KEY: str = pydantic.Field(
        ...,
        description="The routing key for the RabbitMQ priority moderator queue"
    )

    ##### DEAD LETTER

    RABBIT_HYPNOSIS_DEAD_LETTER_QUEUE_NAME: str = pydantic.Field(
        ...,
        description="The name of the RabbitMQ dead letter queue"
    )

    RABBIT_HYPNOSIS_DEAD_LETTER_QUEUE_ROUTING_KEY: str = pydantic.Field(
        ...,
        description="The routing key for the RabbitMQ dead letter queue"
    )
    
    ##### LOGGING QUEUE
    RABBIT_HYPNOSIS_LOGGING_QUEUE_NAME: str = pydantic.Field(
        ...,
        description="The name of the RabbitMQ logging queue"
    )

    RABBIT_HYPNOSIS_LOGGING_QUEUE_ROUTING_KEY: str = pydantic.Field(
        ...,
        description="The routing key for the RabbitMQ logging queue"
    )