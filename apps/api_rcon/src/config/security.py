from typing import Optional
import pydantic
from pydantic_settings import BaseSettings

class SecuritySettings(BaseSettings):
    API_KEY: str = pydantic.Field(
        default="default_secret_key",
        validation_alias="API_KEY",
        description="Global API Key for accessing the endpoints"
    )
    API_KEY_NAME: str = pydantic.Field(
        default="X-API-Key",
        validation_alias="API_KEY_NAME",
        description="Header name for the API Key"
    )
    TEBEX_WEBHOOK_SECRET: Optional[str] = pydantic.Field(
        default=None,
        validation_alias="TEBEX_WEBHOOK_SECRET",
        description="Secret key to verify Tebex webhook HMAC signatures"
    )
    TEBEX_SERVER_SECRET: Optional[str] = pydantic.Field(
        default=None,
        validation_alias="TEBEX_SERVER_SECRET",
        description="Tebex Game Server Secret Key"
    )
