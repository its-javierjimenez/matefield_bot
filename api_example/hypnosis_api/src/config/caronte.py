import typing
import pydantic
from hypnosis_config import BaseSettings


class CaronteSettings(BaseSettings):

    CARONTE_MARK_ERROR_TASK_AS: typing.Literal["error", "review", "critical"] = pydantic.Field(
        default="critical",
        env="CARONTE_MARK_ERROR_TASK_AS"
    )