import pydantic
from pydantic_settings import BaseSettings


class ConnectionSettings(BaseSettings):
    DATABASE_URL: str = pydantic.Field(
        default="postgresql+asyncpg://postgres:password@127.0.0.1:5432/wardogs",
        validation_alias="DATABASE_URL",
        description="Database connection string",
    )

    RCON_URL: str = pydantic.Field(
        default="http://127.0.0.1:7776",
        validation_alias="RCON_URL",
        description="URL for the game server RCON API",
    )

    RCON_PASSWORD: str = pydantic.Field(
        default="",
        validation_alias="RCON_PASSWORD",
        description="Password for the game server RCON API",
    )

    PUBLIC_API_URL: str = pydantic.Field(
        default="",
        validation_alias="PUBLIC_API_URL",
        description="Publicly accessible URL of the API for direct downloads",
    )

    BACKUP_DIR: str = pydantic.Field(
        default="data/backups",
        validation_alias="BACKUP_DIR",
        description="Directory where SQL database backups are saved",
    )

    BACKUP_RETENTION_DAYS: int = pydantic.Field(
        default=14,
        validation_alias="BACKUP_RETENTION_DAYS",
        description="Number of days to keep automated SQL backups",
    )

    BACKUP_KEEP_MIN: int = pydantic.Field(
        default=10,
        validation_alias="BACKUP_KEEP_MIN",
        description="Minimum number of backup files to keep regardless of age",
    )

    SERVER_HOST: str = pydantic.Field(
        default="0.0.0.0",
        validation_alias="SERVER_HOST",
        description="Bind host for the uvicorn dev server",
    )

    SERVER_PORT: int = pydantic.Field(
        default=8000,
        validation_alias="SERVER_PORT",
        description="Bind port for the uvicorn dev server",
    )
