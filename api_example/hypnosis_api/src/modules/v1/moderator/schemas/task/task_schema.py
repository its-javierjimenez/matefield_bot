from pydantic import Field, ConfigDict
from .settings_schema import Settings
from src.modules.v1.shared.schemas.task import task_schema


class ModeratorTaskDTO(task_schema.TaskDTO):
    """
    Model for a moderator task.
    """
    model_config = ConfigDict(
        extra="allow",
        validate_by_alias=True,
        validate_by_name=True,
        serialize_by_alias=True,
    )

class Task(ModeratorTaskDTO):
    """
    Model for a task.
    """
    model_config = ConfigDict(
        extra="allow",
        validate_by_alias=True,
        validate_by_name=True,
        serialize_by_alias=True,
    )

    settings: Settings = Field(
        ...,
        description="The settings for the moderator"
    )

if __name__ == "__main__":
    
    print(
        Task.model_json_schema(by_alias=True, mode="serialization")
    )
