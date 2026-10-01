"""
API key guard dependency for FastAPI.

Usage::

    from src.security.guard import verify_api_key_guard

    @router.get("/protected", dependencies=[Depends(verify_api_key_guard)])
    async def my_endpoint(): ...

Security notes:
- Uses ``secrets.compare_digest`` for constant-time comparison to prevent
  timing-based side-channel attacks.
- Returns 401 (not 403) when the header is missing, and 403 when the key
  is present but invalid, following RFC 7235 semantics.
"""
import secrets
from fastapi import Security, HTTPException
from fastapi.security.api_key import APIKeyHeader

from src.config import ENVIRONMENT_SETTINGS

_settings = ENVIRONMENT_SETTINGS.SECURITY_SETTINGS

api_key_header = APIKeyHeader(name=_settings.API_KEY_NAME, auto_error=False)


async def verify_api_key_guard(api_key: str = Security(api_key_header)) -> str:
    """
    FastAPI dependency that validates the incoming API key header.

    Raises:
        HTTPException 401: when the header is absent.
        HTTPException 403: when the header is present but the value is wrong.

    Returns the validated key string so it can be captured in route signatures
    if needed (e.g. for audit logging).
    """
    expected = _settings.API_KEY
    if not api_key:
        raise HTTPException(status_code=401, detail="API key required")
    if not secrets.compare_digest(api_key, expected):
        raise HTTPException(status_code=403, detail="Could not validate credentials")
    return api_key
