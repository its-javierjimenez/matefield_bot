import pydantic
from hypnosis_config import BaseSettings


class TaskLoggingSettings(BaseSettings):
    """
    Configuraciones relacionadas con el logging de tareas.
    """

    LOGGING_DATABASE_NAME: str = pydantic.Field(
        default="logging",
        description="El nombre de la base de datos para logging de tareas"
    )

    LOGGING_PIPELINE_EVENTS_COLLECTION: str = pydantic.Field(
        default="pipeline_events",
        description="El nombre de la colección para eventos de pipeline en la base de datos de logging"
    )

    LOGGING_PIPELINE_EVENTS_WEBHOOKS_COLLECTION: str = pydantic.Field(
        default="pipeline_events_webhooks",
        description="El nombre de la colección para webhooks de eventos de pipeline en la base de datos de logging"
    )