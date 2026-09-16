import pydantic
from hypnosis_config import BaseSettings


class ExportSettings(BaseSettings):

    EXPORT_SETTINGS_COLLECTION : str = pydantic.Field(
        default="export_settings",
        env="EXPORT_SETTINGS_COLLECTION"
    )

    EXPORT_SETTINGS_DATABASE: str = pydantic.Field(
        default="settings",
        env="EXPORT_SETTINGS_DATABASE"
    )

    EXPORT_AUDIOS_FOLDER: str = pydantic.Field(
        default="final_audios",
        env="EXPORT_AUDIOS_FOLDER"
    )

    EXPORT_TEMPLATES_FOLDER: str = pydantic.Field(
        default="export/audio_templates",
        env="EXPORT_TEMPLATES_FOLDER"
    )