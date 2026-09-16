import pydantic
from hypnosis_config import BaseSettings


class ConnectionSettings(BaseSettings):

    MENTAL_API_URL: str = pydantic.Field(
        default="http://localhost:8001",
        description="The API URL for the MENTAL service"
    )

    MENTAL_API_TOKEN: str = pydantic.Field(
        ...,
        description="The API token for the MENTAL service"
    )

    MENTAL_API_STORAGE_URL: str = pydantic.Field(
        default="http://localhost:8002",
        description="The API URL for the MENTAL storage service"
    )

    MENTAL_API_STORAGE_CLIENT: str = pydantic.Field(
        default="digitalOcean",
        description="The API URL for the MENTAL storage client"
    )

    MONGO_DB_URL: str = pydantic.Field(
        default="mongodb://localhost:27017",
        description="The MongoDB connection URL"
    )