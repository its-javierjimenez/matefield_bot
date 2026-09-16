from typing import Optional
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse

from hypnosis_utils.logger import getLogger
from src.config import ENVIRONMENT_SETTINGS

LOGGER = getLogger("security.guard")

PUBLIC_PATH_PREFIXES = (
    "/docs",
    "/redoc",
    "/openapi.json",
    "/health",
)

async def verify_api_key_guard(request: Request) -> Optional[Response]:
    """Custom request check for FastAPI Guard that validates API Key."""

    if any(request.url.path.startswith(prefix) for prefix in PUBLIC_PATH_PREFIXES):
        return None

    api_key = request.headers.get("x-api-key")
    
    if not api_key:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Missing API Key"}
        )

    expected_key = ENVIRONMENT_SETTINGS.SECURITY_SETTINGS.SECURITY_API_KEY
    
    if api_key != expected_key:
        LOGGER.warning(f"Invalid API Key attempt: {api_key[:4]}***")
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Invalid API Key"}
        )

    return None
