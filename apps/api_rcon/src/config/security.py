"""
Security settings loaded from environment variables.

All Discord-related config lives here so auth.py and discord_oauth_service.py
read from a single, consistent source after load_dotenv() runs — avoiding the
os.environ.get() scatter that could silently return None before dotenv loads.
"""
from typing import Optional
import pydantic
from pydantic_settings import BaseSettings


class SecuritySettings(BaseSettings):
    API_KEY: str = pydantic.Field(
        default="default_secret_key",
        validation_alias="API_KEY",
        description="Global API Key for accessing the endpoints",
    )
    API_KEY_NAME: str = pydantic.Field(
        default="X-API-Key",
        validation_alias="API_KEY_NAME",
        description="Header name for the API Key",
    )
    TEBEX_WEBHOOK_SECRET: Optional[str] = pydantic.Field(
        default=None,
        validation_alias="TEBEX_WEBHOOK_SECRET",
        description="Secret key to verify Tebex webhook HMAC signatures",
    )
    TEBEX_SERVER_SECRET: Optional[str] = pydantic.Field(
        default=None,
        validation_alias="TEBEX_SERVER_SECRET",
        description="Tebex Game Server Secret Key",
    )

    # --- Discord integration ------------------------------------------------
    # Used by auth.py (immediate role assignment) and discord_oauth_service.py.
    # Having them here unifies access and prevents the silent-None bug from
    # reading os.environ before load_dotenv() has run.

    DISCORD_TOKEN: Optional[str] = pydantic.Field(
        default=None,
        validation_alias="DISCORD_TOKEN",
        description="Discord bot token for immediate post-link role assignment",
    )
    DISCORD_GUILD_ID: Optional[str] = pydantic.Field(
        default=None,
        validation_alias="DISCORD_GUILD_ID",
        description="Target Discord guild/server ID",
    )
    DISCORD_CLIENT_ID: Optional[str] = pydantic.Field(
        default=None,
        validation_alias="DISCORD_CLIENT_ID",
        description="Discord OAuth2 application client ID",
    )
    DISCORD_CLIENT_SECRET: Optional[str] = pydantic.Field(
        default=None,
        validation_alias="DISCORD_CLIENT_SECRET",
        description="Discord OAuth2 application client secret",
    )
