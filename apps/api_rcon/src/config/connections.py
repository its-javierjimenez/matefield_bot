import pydantic
from pydantic_settings import BaseSettings

class ConnectionSettings(BaseSettings):
    DATABASE_URL: str = pydantic.Field(
        default="postgresql+asyncpg://postgres:password@127.0.0.1:5432/wardogs",
        env="DATABASE_URL",
        description="MySQL database connection string"
    )

    RCON_URL: str = pydantic.Field(
        default="http://127.0.0.1:7776",
        env="RCON_URL",
        description="URL for the game server RCON API"
    )

    RCON_PASSWORD: str = pydantic.Field(
        default="test",
        description="Password for the game server RCON API"
    )

    BACKUP_DIR: str = pydantic.Field(
        default="backups",
        description="Directory on disk to store database backups"
    )

    BACKUP_INTERVAL_HOURS: int = pydantic.Field(
        default=24,
        description="Interval in hours between automated backups"
    )

    BACKUP_RETENTION_DAYS: int = pydantic.Field(
        default=14,
        description="Days to retain backup files"
    )

    PUBLIC_API_URL: str = pydantic.Field(
        default="",
        description="Public base URL for external links (e.g. http://localhost:8000)"
    )
