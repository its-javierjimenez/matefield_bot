import pytest
import time
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.main import app
from src.connections.databases.db import Player
from wardogs_schemas.steam_token import create_steam_link_token, verify_steam_link_token

@pytest.mark.asyncio
async def test_steam_token_creation_and_verification():
    secret = "test-secret-key-12345"
    token = create_steam_link_token("123456789", secret, guild_id="987654321", expires_in=60)
    
    # 1. Valid token
    payload = verify_steam_link_token(token, secret)
    assert payload is not None
    assert payload["discord_id"] == "123456789"
    assert payload["guild_id"] == "987654321"
    
    # 2. Wrong secret
    assert verify_steam_link_token(token, "wrong-secret") is None
    
    # 3. Tampered token
    tampered = token[:-4] + "abcd"
    assert verify_steam_link_token(tampered, secret) is None
    
    # 4. Expired token
    expired_token = create_steam_link_token("123456789", secret, expires_in=-10)
    assert verify_steam_link_token(expired_token, secret) is None

@pytest.mark.asyncio
async def test_steam_login_redirect(client: AsyncClient):
    secret = "secret_key"
    with patch("src.config.ENVIRONMENT_SETTINGS.SECURITY_SETTINGS.API_KEY", secret), \
         patch("src.config.ENVIRONMENT_SETTINGS.CONNECTIONS_SETTINGS.PUBLIC_API_URL", "http://testserver"):
        
        # Token inválido
        resp_invalid = await client.get("/api/v1/auth/steam/login?token=invalid.token")
        assert resp_invalid.status_code == 400
        assert "Enlace Expirado o Inválido" in resp_invalid.text
        
        # Token válido
        token = create_steam_link_token("123456789", secret, expires_in=600)
        resp = await client.get(f"/api/v1/auth/steam/login?token={token}", follow_redirects=False)
        assert resp.status_code == 303
        location = resp.headers["location"]
        assert "steamcommunity.com/openid/login" in location
        assert "checkid_setup" in location
        assert ("token=" in location or "token%3D" in location)

@pytest.mark.asyncio
async def test_steam_callback_success(client: AsyncClient, session: AsyncSession):
    secret = "secret_key"
    discord_id = "555666777"
    steam_id = "76561198000000888"
    token = create_steam_link_token(discord_id, secret, expires_in=600)
    
    mock_post_resp = MagicMock()
    mock_post_resp.text = "ns:http://specs.openid.net/auth/2.0\nis_valid:true\n"
    
    mock_steam_summary = {
        "personaname": "GamerPro",
        "avatarfull": "https://steamcdn.test/avatar.jpg"
    }

    with patch("src.config.ENVIRONMENT_SETTINGS.SECURITY_SETTINGS.API_KEY", secret), \
         patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_post_resp)), \
         patch("src.modules.v1.routers.auth.get_player_summary", new=AsyncMock(return_value=mock_steam_summary)):
        
        params = {
            "token": token,
            "openid.mode": "id_res",
            "openid.claimed_id": f"https://steamcommunity.com/openid/id/{steam_id}",
            "openid.identity": f"https://steamcommunity.com/openid/id/{steam_id}",
            "openid.sig": "validsig123"
        }
        resp = await client.get("/api/v1/auth/steam/callback", params=params)
        assert resp.status_code == 200
        assert "¡Bienvenido, GamerPro!" in resp.text
        assert steam_id in resp.text
        assert discord_id in resp.text
        
        # Verificar en DB
        player = await session.get(Player, steam_id)
        assert player is not None
        assert player.discord_id == discord_id
        assert player.in_game_name == "GamerPro"
        assert player.avatar_url == "https://steamcdn.test/avatar.jpg"

