import pymongo
from src.config import ENVIRONMENT_SETTINGS

MONGO_CLIENT = pymongo.AsyncMongoClient(
    ENVIRONMENT_SETTINGS.CONNECTIONS_SETTINGS.MONGO_DB_URL,
)