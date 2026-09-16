import pydantic
from hypnosis_config import BaseSettings


class ModeratorSettings(BaseSettings):

    MODERATOR_SETTINGS_COLLECTION : str = pydantic.Field(
        default="moderator_settings",
        env="MODERATOR_SETTINGS_COLLECTION"
    )

    MODERATOR_SETTINGS_DATABASE: str = pydantic.Field(
        default="settings",
        env="MODERATOR_SETTINGS_DATABASE"
    )