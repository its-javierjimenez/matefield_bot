import pydantic
from hypnosis_config import BaseSettings


class SecuritySettings(BaseSettings):

    SECURITY_API_KEY: str = pydantic.Field(
        default="changeme",
        description="The API key for securing the endpoints"
    )

    SECURITY_SIGNATURE_SECRET: str = pydantic.Field(
        default="supersecret",
        description="The secret used for signing requests"
    )

    GUARD_RATE_LIMIT: int = pydantic.Field(
        default=100,
        description="Rate limit for the API"
    )

    GUARD_RATE_LIMIT_WINDOW_SECONDS: int = pydantic.Field(
        default=60,
        description="Rate limit window in seconds"
    )