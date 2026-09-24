import hashlib
import hmac
import logging
import time

from src.config import ENVIRONMENT_SETTINGS

logger = logging.getLogger("wardogs.security.tokens")


def generate_secure_download_token(filename: str, expires_in_seconds: int = 1800) -> str:
    """Generates a stateless, tamper-proof HMAC-SHA256 download token for any file."""
    expires_at = int(time.time()) + expires_in_seconds
    message = f"{filename}:{expires_at}".encode("utf-8")
    secret = ENVIRONMENT_SETTINGS.SECURITY_SETTINGS.API_KEY.encode("utf-8")
    sig = hmac.new(secret, message, hashlib.sha256).hexdigest()
    return f"{expires_at}.{sig}"


def verify_secure_download_token(filename: str, token: str) -> bool:
    """Verifies that an HMAC download token is authentic and unexpired."""
    try:
        parts = token.split(".", 1)
        if len(parts) != 2:
            return False
        expires_at_str, sig = parts
        expires_at = int(expires_at_str)
        if time.time() > expires_at:
            return False
        message = f"{filename}:{expires_at}".encode("utf-8")
        secret = ENVIRONMENT_SETTINGS.SECURITY_SETTINGS.API_KEY.encode("utf-8")
        expected_sig = hmac.new(secret, message, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected_sig, sig)
    except Exception as e:
        logger.warning(f"Error verifying download token for {filename}: {e}")
        return False
