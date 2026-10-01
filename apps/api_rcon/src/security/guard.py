"""
Authentication and authorization guards for FastAPI.

Provides:
- ``verify_api_key_guard``: Validates incoming requests using either the API key header
  (for internal/microservice calls) or a valid admin session cookie/token (for admin dashboard calls).
- ``create_admin_session_token`` / ``verify_admin_session_token``: HMAC-SHA256 signed session
  tokens for the admin dashboard.
- ``get_current_admin_session``: Dependency that enforces an active admin session.
- ``extract_admin_session_token``: Helper to retrieve session token from cookie or Authorization header.
"""
import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
from typing import Any, Dict, Optional

from fastapi import HTTPException, Request, Security
from fastapi.security.api_key import APIKeyHeader

from src.config import ENVIRONMENT_SETTINGS

logger = logging.getLogger("wardogs.security.guard")

_settings = ENVIRONMENT_SETTINGS.SECURITY_SETTINGS
api_key_header = APIKeyHeader(name=_settings.API_KEY_NAME, auto_error=False)


def _get_admin_session_secret() -> str:
    return _settings.ADMIN_SESSION_SECRET or _settings.API_KEY


def create_admin_session_token(payload: Dict[str, Any], expires_in_seconds: int = 604800) -> str:
    """Creates a signed HMAC-SHA256 admin session token."""
    now = int(time.time())
    token_payload = {
        **payload,
        "iat": payload.get("iat", now),
        "exp": now + expires_in_seconds,
    }
    payload_bytes = json.dumps(token_payload, separators=(",", ":")).encode("utf-8")
    encoded_payload = base64.urlsafe_b64encode(payload_bytes).decode("ascii").rstrip("=")
    secret = _get_admin_session_secret().encode("utf-8")
    sig = hmac.new(secret, encoded_payload.encode("ascii"), hashlib.sha256).digest()
    encoded_sig = base64.urlsafe_b64encode(sig).decode("ascii").rstrip("=")
    return f"{encoded_payload}.{encoded_sig}"


def verify_admin_session_token(token: str) -> Optional[Dict[str, Any]]:
    """Verifies and decodes a signed admin session token. Returns None if invalid or expired."""
    if not token or not isinstance(token, str) or len(token) > 4096:
        return None
    try:
        parts = token.split(".", 1)
        if len(parts) != 2:
            return None
        encoded_payload, encoded_sig = parts
        secret = _get_admin_session_secret().encode("utf-8")
        expected_sig = hmac.new(secret, encoded_payload.encode("ascii"), hashlib.sha256).digest()
        actual_sig = base64.urlsafe_b64decode(encoded_sig + "=" * (-len(encoded_sig) % 4))
        if not hmac.compare_digest(expected_sig, actual_sig):
            return None

        payload_bytes = base64.urlsafe_b64decode(encoded_payload + "=" * (-len(encoded_payload) % 4))
        payload = json.loads(payload_bytes.decode("utf-8"))
        if not isinstance(payload, dict) or payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None


def extract_admin_session_token(request: Request) -> Optional[str]:
    """Extracts the admin session token from cookies or the Authorization Bearer header."""
    cookie_token = request.cookies.get("admin_session")
    if cookie_token:
        return cookie_token

    auth_header = request.headers.get("Authorization") or request.headers.get("authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()

    return None


async def get_current_admin_session(request: Request) -> Dict[str, Any]:
    """FastAPI dependency requiring an active admin session."""
    token = extract_admin_session_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Sesión de administrador no encontrada")
    session_data = verify_admin_session_token(token)
    if not session_data or not session_data.get("is_admin"):
        raise HTTPException(status_code=401, detail="Sesión inválida o expirada")
    return session_data


async def verify_api_key_guard(
    request: Request,
    api_key: Optional[str] = Security(api_key_header),
) -> str:
    """
    FastAPI dependency validating access via either:
    1. Valid X-API-Key header.
    2. Valid admin session (cookie or Bearer token with is_admin=True).

    Raises HTTPException 403 when neither credential is valid.
    """
    if api_key and secrets.compare_digest(api_key, _settings.API_KEY):
        return api_key

    token = extract_admin_session_token(request)
    if token:
        session_data = verify_admin_session_token(token)
        if session_data and session_data.get("is_admin") is True:
            return "admin_session"

    raise HTTPException(status_code=403, detail="Could not validate credentials")
