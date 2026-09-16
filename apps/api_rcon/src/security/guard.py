from fastapi import Security, HTTPException
from fastapi.security.api_key import APIKeyHeader

from src.config import ENVIRONMENT_SETTINGS

api_key_header = APIKeyHeader(
    name=ENVIRONMENT_SETTINGS.SECURITY_SETTINGS.API_KEY_NAME, 
    auto_error=False
)

async def verify_api_key_guard(api_key_header: str = Security(api_key_header)):
    if api_key_header == ENVIRONMENT_SETTINGS.SECURITY_SETTINGS.API_KEY:
        return api_key_header
    raise HTTPException(status_code=403, detail="Could not validate credentials")
