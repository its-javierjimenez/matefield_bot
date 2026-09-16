import pydantic
from hypnosis_config import BaseSettings

from .connections import ConnectionSettings
from .rabbit import RabbitSettings
from .sentry import SentrySettings
from .export import ExportSettings
from .maker import MakerSettings
from .security import SecuritySettings
from .decorator import DecoratorSettings
from .caronte import CaronteSettings
from .task_logging import TaskLoggingSettings
from .moderator import ModeratorSettings


class EnvironmentSettings(BaseSettings):

    WEB_CONCURRENCY: int = pydantic.Field(
        default=1,
        description="The number of worker processes for handling requests"
    )

    SECURITY_SETTINGS: SecuritySettings = pydantic.Field(
        default_factory=SecuritySettings,
        description="Security configuration"
    )

    SENTRY_SETTINGS: SentrySettings = pydantic.Field(
        default_factory=SentrySettings,
        description="Sentry configuration"
    )

    CONNECTIONS_SETTINGS: ConnectionSettings = pydantic.Field(
        default_factory=ConnectionSettings,
        description="Database connection configuration"
    )

    RABBIT_SETTINGS: RabbitSettings = pydantic.Field(
        default_factory=RabbitSettings,
        description="RabbitMQ configuration"
    )

    EXPORT_SETTINGS: ExportSettings = pydantic.Field(
        default_factory=ExportSettings,
        description="Export configuration"
    )

    MAKER_SETTINGS: MakerSettings = pydantic.Field(
        default_factory=MakerSettings,
        description="Maker configuration"
    )

    DECORATOR_SETTINGS: DecoratorSettings = pydantic.Field(
        default_factory=DecoratorSettings,
        description="Decorator configuration"
    )

    CARONTE_SETTINGS: CaronteSettings = pydantic.Field(
        default_factory=CaronteSettings,
        description="Caronte configuration"
    )

    TASK_LOGGING_SETTINGS: TaskLoggingSettings = pydantic.Field(
        default_factory=TaskLoggingSettings,
        description="Task logging configuration"
    )

    MODERATOR_SETTINGS: ModeratorSettings = pydantic.Field(
        default_factory=ModeratorSettings,
        description="Moderator configuration"
    )

ENVIRONMENT_SETTINGS = EnvironmentSettings()