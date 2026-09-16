import pydantic
from hypnosis_config import BaseSettings


class SentrySettings(BaseSettings):

    SENTRY_DSN: str = pydantic.Field(
        ...,
        description="The Sentry DSN"
    )

    SENTRY_SAMPLE_RATE: float = pydantic.Field(
        ...,
        description="The Sentry sample rate"
    )

    SENTRY_ENVIRONMENT: str = pydantic.Field(
        ...,
        description="The Sentry environment"
    )

    SENTRY_RELEASE: str = pydantic.Field(
        ...,
        description="The Sentry release"
    )

    SENTRY_ENABLE_LOGS: bool = pydantic.Field(
        ...,
        description="Enable Sentry logging"
    )