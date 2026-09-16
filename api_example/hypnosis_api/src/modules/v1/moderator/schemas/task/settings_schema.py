from pydantic import BaseModel, Field, ConfigDict
from src.modules.v1.shared.schemas.task.generation_settings import TextGenerationSettings

class SimpleModerationCategorySettings(BaseModel):

    name : str = Field(
        ...,
        description="Name of the moderation category"
    )

    maxOffensivePointsAllowed : int = Field(
        ...,
        description="Maximum offensive points allowed for this category"
    )

    words : dict[str, int] = Field(
        ...,
        description="Mapping of words to their offensive points",
        examples=[{"badword1": 5, "badword2": 3}]
    )

class SimpleModerationSettings(BaseModel):
    """
    Model for simple moderation settings.
    """
    model_config = ConfigDict(
        extra="allow",
        validate_by_alias=True,
        validate_by_name=True,
        serialize_by_alias=True,
    )

    maxOffensivePointsAllowed : int = Field(
        ...,
        description="Maximum offensive points allowed before flagging"
    )

    categories : list[SimpleModerationCategorySettings] = Field(
        ...,
        description="Mapping of words to their moderation settings"
    )

class Settings(BaseModel):
    """
    Model for task settings.
    """
    model_config = ConfigDict(
        extra="allow",
        validate_by_alias=True,
        validate_by_name=True,
        serialize_by_alias=True,
    )

    language : str = Field(
        ...,
        alias="language",
        description="The language setting for the task"
    )

    simpleModerationSettings : SimpleModerationSettings = Field(
        ...,
        alias="simpleModerationSettings",
        description="Mapping for simple moderation settings",
    )

    aiModeratorSettings: TextGenerationSettings = Field(
        ...,
        alias="aiModeratorSettings",
        description="Settings related to AI moderation"
    )
