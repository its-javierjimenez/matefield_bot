import pydantic
from pydantic_settings import BaseSettings

class SecuritySettings(BaseSettings):
    API_KEY: str = pydantic.Field(
        default="default_secret_key",
        env="API_KEY",
        description="Global API Key for accessing the endpoints"
    )
    API_KEY_NAME: str = pydantic.Field(
        default="X-API-Key",
        env="API_KEY_NAME",
        description="Header name for the API Key"
    )
