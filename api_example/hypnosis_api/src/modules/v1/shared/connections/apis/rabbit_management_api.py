"""HTTP client for RabbitMQ management API interactions."""

import httpx

from src.config import ENVIRONMENT_SETTINGS

RABBIT_MANAGEMENT_CLIENT = httpx.AsyncClient(
    base_url=ENVIRONMENT_SETTINGS.RABBIT_SETTINGS.RABBIT_MANAGEMENT_URL,
    auth=(
        ENVIRONMENT_SETTINGS.RABBIT_SETTINGS.RABBIT_MANAGEMENT_USERNAME,
        ENVIRONMENT_SETTINGS.RABBIT_SETTINGS.RABBIT_MANAGEMENT_PASSWORD,
    ),
    headers=httpx.Headers(
        {
            "Accept": "application/json",
            "connection": "close",
        }
    ),
    timeout=httpx.Timeout(
        timeout=ENVIRONMENT_SETTINGS.RABBIT_SETTINGS.RABBIT_MANAGEMENT_TIMEOUT_SECONDS,
    ),
)
