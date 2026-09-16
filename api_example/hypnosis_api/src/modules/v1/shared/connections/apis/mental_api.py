import httpx
from src.config import ENVIRONMENT_SETTINGS

MENTAL_API_CLIENT = httpx.AsyncClient(
    base_url=ENVIRONMENT_SETTINGS.CONNECTIONS_SETTINGS.MENTAL_API_URL,
    headers=httpx.Headers(
        {
            "Authorization": f"Bearer {ENVIRONMENT_SETTINGS.CONNECTIONS_SETTINGS.MENTAL_API_TOKEN}",
            "connection": "close"
        }
    ),
    timeout=httpx.Timeout(timeout=60)
)