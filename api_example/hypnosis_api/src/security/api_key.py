"""Helpers to validate API key authentication for HTTP entrypoints."""

from typing import Optional

from fastapi import HTTPException, Request, Security, status
from fastapi.security.api_key import APIKeyHeader

from src.config import ENVIRONMENT_SETTINGS
from .guard import PUBLIC_PATH_PREFIXES as GUARDED_PUBLIC_PATHS

API_KEY_HEADER_NAME = "x-api-key"


class SafeApiKeyHeader(APIKeyHeader):
    """API key header scheme that skips public paths so Swagger can load."""

    async def __call__(self, request: Request) -> Optional[str]:
        if _is_public_path(request.url.path):
            return None
        return await super().__call__(request)


apiKeyScheme = SafeApiKeyHeader(
    name=API_KEY_HEADER_NAME,
    auto_error=True,
    scheme_name="API Key Header",
    description="API Key requerida mediante el encabezado x-api-key.",
)


async def verify_api_key(
    api_key: Optional[str] = Security(apiKeyScheme),
) -> str:
    expected = ENVIRONMENT_SETTINGS.SECURITY_SETTINGS.SECURITY_API_KEY
    if api_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key",
        )
    return api_key


def _is_public_path(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in GUARDED_PUBLIC_PATHS)


__all__ = ["apiKeyScheme", "verify_api_key", "API_KEY_HEADER_NAME"]
