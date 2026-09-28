import pydantic
from pydantic_settings import BaseSettings

class ConnectionSettings(BaseSettings):
    DATABASE_URL: str = pydantic.Field(
        default="postgresql+asyncpg://postgres:password@127.0.0.1:5432/wardogs",
        validation_alias="DATABASE_URL",
        description="Database connection string"
    )

    RCON_URL: str = pydantic.Field(
        default="http://127.0.0.1:7776",
        validation_alias="RCON_URL",
        description="URL for the game server RCON API"
    )

    RCON_PASSWORD: str = pydantic.Field(
        default="test",
        validation_alias="RCON_PASSWORD",
        description="Password for the game server RCON API"
    )

    PUBLIC_API_URL: str = pydantic.Field(
        default="",
        validation_alias="PUBLIC_API_URL",
        description="Publicly accessible URL of the API for direct downloads"
    )

    BACKUP_DIR: str = pydantic.Field(
        default="data/backups",
        validation_alias="BACKUP_DIR",
        description="Directory where SQL database backups are saved"
    )

    DISCORD_GENERAL_CHANNEL_URL: str = pydantic.Field(
        default="https://discord.com/channels/1187116902217171004/1537509330109202594",
        validation_alias="DISCORD_GENERAL_CHANNEL_URL",
        description="URL of the 'general' Discord channel for the auth callback page"
    )

    DISCORD_REQUEST_HELP_CHANNEL_URL: str = pydantic.Field(
        default="https://discord.com/channels/1187116902217171004/1552778290253664347",
        validation_alias="DISCORD_REQUEST_HELP_CHANNEL_URL",
        description="URL of the 'pedir-ayuda' Discord channel for the auth callback page"
    )
