import pydantic
from pydantic_settings import BaseSettings

from src.config.connections import ConnectionSettings
from src.config.security import SecuritySettings

class EnvironmentSettings(BaseSettings):
    SECURITY_SETTINGS: SecuritySettings = pydantic.Field(
        default_factory=SecuritySettings,
        description="Security configuration"
    )

    CONNECTIONS_SETTINGS: ConnectionSettings = pydantic.Field(
        default_factory=ConnectionSettings,
        description="Database and API connection configuration"
    )

ENVIRONMENT_SETTINGS = EnvironmentSettings()
