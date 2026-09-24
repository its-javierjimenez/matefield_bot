import hmac
import hashlib
import json
import base64
import time
from typing import Optional, Dict, Any

def create_steam_link_token(
    discord_id: str,
    secret_key: str,
    guild_id: Optional[str] = None,
    expires_in: int = 600
) -> str:
    """
    Genera un token seguro firmado con HMAC-SHA256 para el flujo de vinculación de Steam OpenID.
    Por defecto expira en 10 minutos (600 segundos).
    """
    payload = {
        "discord_id": str(discord_id),
        "guild_id": str(guild_id) if guild_id else None,
        "exp": int(time.time()) + expires_in
    }
    payload_bytes = json.dumps(payload, separators=(',', ':')).encode('utf-8')
    payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode('ascii').rstrip('=')
    
    sig = hmac.new(secret_key.encode('utf-8'), payload_b64.encode('ascii'), hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(sig).decode('ascii').rstrip('=')
    
    return f"{payload_b64}.{sig_b64}"

def verify_steam_link_token(token: str, secret_key: str) -> Optional[Dict[str, Any]]:
    """
    Verifica la autenticidad y vigencia de un token de vinculación de Steam.
    Devuelve el payload con discord_id y guild_id si es válido, o None si expiró o fue alterado.
    """
    try:
        parts = token.split('.')
        if len(parts) != 2:
            return None
        payload_b64, sig_b64 = parts
        
        expected_sig = hmac.new(secret_key.encode('utf-8'), payload_b64.encode('ascii'), hashlib.sha256).digest()
        
        pad_sig = len(sig_b64) % 4
        sig_b64_padded = sig_b64 + ('=' * (4 - pad_sig) if pad_sig else '')
        actual_sig = base64.urlsafe_b64decode(sig_b64_padded)
        
        if not hmac.compare_digest(expected_sig, actual_sig):
            return None
        
        pad_payload = len(payload_b64) % 4
        payload_b64_padded = payload_b64 + ('=' * (4 - pad_payload) if pad_payload else '')
        payload_bytes = base64.urlsafe_b64decode(payload_b64_padded)
        payload = json.loads(payload_bytes.decode('utf-8'))
        
        if payload.get("exp", 0) < time.time():
            return None
            
        return payload
    except Exception:
        return None
