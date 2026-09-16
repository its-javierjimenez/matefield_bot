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
        env="RCON_PASSWORD",
        description="Password for the game server RCON API"
    )
