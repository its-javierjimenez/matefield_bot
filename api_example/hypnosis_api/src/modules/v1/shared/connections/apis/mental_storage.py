import httpx
from hypnosis_utils.logger import getLogger
from src.config import ENVIRONMENT_SETTINGS

LOGGER = getLogger("v1.shared.connections.mental_storage")

MENTAL_STORAGE_CLIENT = httpx.AsyncClient(
    base_url=f"{ENVIRONMENT_SETTINGS.CONNECTIONS_SETTINGS.MENTAL_API_STORAGE_URL}/file",
    headers=httpx.Headers(
        {
            "storageClient" : ENVIRONMENT_SETTINGS.CONNECTIONS_SETTINGS.MENTAL_API_STORAGE_CLIENT,
            "connection" : "close"
        }
    ),
    timeout=httpx.Timeout(
        timeout=15
    )
)

LOGGER.info(f"[SHARED][STORAGE] Mental Storage Client initialized with base URL: {MENTAL_STORAGE_CLIENT.base_url} | {MENTAL_STORAGE_CLIENT.headers}")