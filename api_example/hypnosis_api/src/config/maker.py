import pydantic
from hypnosis_config import BaseSettings


class MakerSettings(BaseSettings):

    MAKER_SETTINGS_COLLECTION : str = pydantic.Field(
        default="maker_settings",
        env="MAKER_SETTINGS_COLLECTION"
    )

    MAKER_COMPARATOR_SETTINGS_COLLECTION: str = pydantic.Field(
        default="maker_comparator_settings",
        env="MAKER_COMPARATOR_SETTINGS_COLLECTION"
    )

    MAKER_SETTINGS_DATABASE: str = pydantic.Field(
        default="settings",
        env="MAKER_SETTINGS_DATABASE"
    )

    MAKER_ZIPS_FOLDER: str = pydantic.Field(
        default="maker/audio_zips",
        env="MAKER_ZIPS_FOLDER"
    )

    MAKER_STATIC_AUDIOS_FOLDER: str = pydantic.Field(
        default="maker/static_audios",
        env="MAKER_STATIC_AUDIOS_FOLDER"
    )