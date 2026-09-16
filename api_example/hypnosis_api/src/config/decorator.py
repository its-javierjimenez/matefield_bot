import pydantic
from hypnosis_config import BaseSettings


class DecoratorSettings(BaseSettings):

    DECORATOR_SETTINGS_COLLECTION : str = pydantic.Field(
        default="decorator_settings",
        env="DECORATOR_SETTINGS_COLLECTION"
    )

    DECORATOR_SETTINGS_DATABASE: str = pydantic.Field(
        default="settings",
        env="DECORATOR_SETTINGS_DATABASE"
    )

    DECORATOR_AUDIOS_CDN: str = pydantic.Field(
        ...,
        env="DECORATOR_AUDIOS_CDN"
    )