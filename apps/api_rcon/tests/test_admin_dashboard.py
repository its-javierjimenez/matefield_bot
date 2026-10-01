import pytest
import time
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient, ASGITransport

from src.main import app
from src.config import ENVIRONMENT_SETTINGS
from src.security.guard import (

    create_admin_session_token,
    verify_admin_session_token,
    verify_api_key_guard,
    get_current_admin_session,
)
from src.modules.v1.services.discord_oauth_service import DiscordOAuthService


def test_admin_session_token_lifecycle():
    payload = {
        "discord_id": "123456789",
        "username": "SuperAdmin",
        "avatar_url": "https://cdn.discordapp.com/embed/avatars/0.png",
        "is_admin": True,
    }

    # 1. Crear y validar token normal
    token = create_admin_session_token(payload, expires_in_seconds=3600)
    assert token is not None
    data = verify_admin_session_token(token)
    assert data is not None
    assert data["discord_id"] == "123456789"
    assert data["username"] == "SuperAdmin"
    assert data["is_admin"] is True
    assert "iat" in data and isinstance(data["iat"], int)

    # 2. Token alterado / firma no válida
    tampered_token = token[:-5] + "abcde"
    assert verify_admin_session_token(tampered_token) is None

    # 3. Token expirado
    expired_token = create_admin_session_token(payload, expires_in_seconds=-10)
    assert verify_admin_session_token(expired_token) is None

    # 4. Token corrupto
    assert verify_admin_session_token("invalid_token_without_period") is None


@pytest.mark.asyncio
async def test_admin_guard_with_real_validation():
    """Prueba que verify_api_key_guard acepte API Key o Admin Session válida."""
    # Retirar override temporal de conftest
    override = app.dependency_overrides.pop(verify_api_key_guard, None)

    expected_api_key = ENVIRONMENT_SETTINGS.SECURITY_SETTINGS.API_KEY
    admin_token = create_admin_session_token({
        "discord_id": "999",
        "username": "TestAdmin",
        "is_admin": True,
    })

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as raw_client:
            # 1. Sin credenciales -> 403
            resp = await raw_client.get("/api/v1/bot/configs")
            assert resp.status_code == 403

            # 2. Con API Key válida -> 200
            resp_api_key = await raw_client.get(
                "/api/v1/bot/configs",
                headers={"X-API-Key": expected_api_key}
            )
            assert resp_api_key.status_code in (200, 307)

            # 3. Con Bearer de Admin Session válida -> 200
            resp_bearer = await raw_client.get(
                "/api/v1/bot/configs",
                headers={"Authorization": f"Bearer {admin_token}"}
            )
            assert resp_bearer.status_code in (200, 307)


            # 4. Con Bearer de no admin -> 403
            non_admin_token = create_admin_session_token({
                "discord_id": "888",
                "username": "RegularUser",
                "is_admin": False,
            })
            resp_non_admin = await raw_client.get(
                "/api/v1/bot/configs",
                headers={"Authorization": f"Bearer {non_admin_token}"}
            )
            assert resp_non_admin.status_code == 403
    finally:
        if override:
            app.dependency_overrides[verify_api_key_guard] = override


@pytest.mark.asyncio
async def test_serve_admin_dashboard_html(client: AsyncClient):
    # Probar ruta raíz /admin y /api/v1/admin
    resp1 = await client.get("/admin")
    assert resp1.status_code == 200
    assert "Admin Dashboard | Matefield Bot" in resp1.text
    assert "Matefield Admin" in resp1.text

    resp2 = await client.get("/api/v1/admin")
    assert resp2.status_code == 200
    assert "Admin Dashboard | Matefield Bot" in resp2.text


@pytest.mark.asyncio
async def test_admin_auth_me_and_logout(client: AsyncClient):
    admin_data = {
        "discord_id": "555123",
        "username": "Commander",
        "avatar_url": "https://cdn.discordapp.com/avatars/555123/avatar.png",
        "steam_id": "76561198000000000",
        "steam_name": "GabeNewell",
        "is_admin": True,
    }
    token = create_admin_session_token(admin_data)

    # 1. /auth/me sin sesión
    resp_unauth = await client.get("/api/v1/admin/auth/me")
    assert resp_unauth.status_code == 401

    # 2. /auth/me con sesión (Bearer)
    resp_auth = await client.get(
        "/api/v1/admin/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp_auth.status_code == 200
    res_json = resp_auth.json()
    assert res_json["authenticated"] is True
    assert res_json["admin"]["username"] == "Commander"
    assert res_json["admin"]["steam_name"] == "GabeNewell"


    # 3. /auth/logout
    resp_logout = await client.post("/api/v1/admin/auth/logout")
    assert resp_logout.status_code == 200
    assert "admin_session" in resp_logout.headers.get("set-cookie", "")


@pytest.mark.asyncio
async def test_discord_oauth_redirect():
    with patch.object(DiscordOAuthService, "get_client_id", return_value="1234567890"), \
         patch.object(DiscordOAuthService, "get_client_secret", return_value="test_secret"):
        url = DiscordOAuthService.get_authorization_url(redirect_uri="http://test/callback")
        assert "discord.com/oauth2/authorize" in url
        assert "client_id=1234567890" in url
        assert "redirect_uri=http%3A%2F%2Ftest%2Fcallback" in url
        assert "identify+guilds+guilds.members.read" in url or "identify%20guilds%20guilds.members.read" in url


@pytest.mark.asyncio
async def test_discord_oauth_callback_csrf_validation(client: AsyncClient):
    # Probar que state discordante devuelva redirect con error CSRF
    resp = await client.get(
        "/api/v1/admin/auth/discord/callback?code=some_code&state=fake_state",
        headers={"Cookie": "oauth_state=legit_state"},
        follow_redirects=False
    )
    assert resp.status_code == 303
    assert "error=csrf_invalid" in resp.headers["location"]


def test_is_secure_request_reverse_proxy():
    from unittest.mock import MagicMock
    from src.modules.v1.routers.admin_dashboard import _is_secure_request, _get_base_url

    req_http = MagicMock()
    req_http.url.scheme = "http"
    req_http.url.netloc = "localhost:8000"
    req_http.headers = {}
    assert _is_secure_request(req_http) is False
    assert _get_base_url(req_http) == "http://localhost:8000"

    req_https = MagicMock()
    req_https.url.scheme = "https"
    req_https.url.netloc = "localhost:8000"
    req_https.headers = {}
    assert _is_secure_request(req_https) is True

    # Proxy simple
    req_forwarded = MagicMock()
    req_forwarded.url.scheme = "http"
    req_forwarded.url.netloc = "internal:8000"
    req_forwarded.headers = {"x-forwarded-proto": "https", "x-forwarded-host": "panel.matefield.com"}
    assert _is_secure_request(req_forwarded) is True
    assert _get_base_url(req_forwarded) == "https://panel.matefield.com"

    # Proxy encadenado (Cloudflare + Nginx: "https, http")
    req_chained = MagicMock()
    req_chained.url.scheme = "http"
    req_chained.url.netloc = "internal:8000"
    req_chained.headers = {"x-forwarded-proto": "https, http", "x-forwarded-host": "panel.matefield.com, proxy.internal"}
    assert _is_secure_request(req_chained) is True
    assert _get_base_url(req_chained) == "https://panel.matefield.com"

    # Ignora placeholders de entorno como <IP_O_DOMINIO_PROD>
    with patch("src.modules.v1.routers.admin_dashboard.os.environ.get", return_value="http://<IP_O_DOMINIO_PROD>:8000"):
        with patch.object(ENVIRONMENT_SETTINGS.CONNECTIONS_SETTINGS, "PUBLIC_API_URL", None):
            assert _get_base_url(req_chained) == "https://panel.matefield.com"



@pytest.mark.asyncio
async def test_admin_steam_callback_conflict_handling(client: AsyncClient):
    """Verifica que un conflicto en la vinculación de Steam ID no se guarde en sesión y retorne error."""
    from fastapi import HTTPException
    from src.modules.v1.services.players_service import PlayersService

    admin_data = {
        "discord_id": "111222333",
        "username": "AdminConflictTester",
        "is_admin": True,
    }
    session_token = create_admin_session_token(admin_data)

    mock_link = AsyncMock(side_effect=HTTPException(
        status_code=400,
        detail="El Steam ID '76561198000000099' ya está vinculado a otra cuenta de Discord."
    ))

    with patch("httpx.AsyncClient.post") as mock_post, \
         patch.object(PlayersService, "link_account", mock_link):
        
        mock_resp = AsyncMock()
        mock_resp.text = "is_valid:true\n"
        mock_post.return_value = mock_resp

        query = (
            "openid.mode=id_res&"
            "openid.claimed_id=https://steamcommunity.com/openid/id/76561198000000099"
        )
        resp = await client.get(
            f"/api/v1/admin/auth/steam/callback?{query}",
            headers={"Cookie": f"admin_session={session_token}"},
            follow_redirects=False
        )

        assert resp.status_code == 303
        assert "error=steam_conflict" in resp.headers["location"]
        # Verificar que la cookie no haya sido sobrescrita con el Steam ID conflictivo
        set_cookie = resp.headers.get("set-cookie")
        assert set_cookie is None or "76561198000000099" not in set_cookie


@pytest.mark.asyncio
async def test_verify_admin_status_case_insensitive_system_role(session):
    """Verifica que roles con tipo 'system' en minúsculas sean reconocidos correctamente."""
    from src.connections.databases.db import Role

    # Insertar rol en minúsculas
    role = Role(code="MOD_TEAM", name="Mod Team", role_type="system", discord_role_id="999777111")
    session.add(role)
    await session.commit()

    with patch.object(DiscordOAuthService, "resolve_guild_id", return_value="123456"):
        with patch("httpx.AsyncClient.get") as mock_get:
            # 1. /users/@me/guilds no admin
            # 2. /users/@me/guilds/123456/member roles devuelve el rol
            def mock_get_router(url, *args, **kwargs):
                resp = AsyncMock()
                if url.endswith("/guilds"):
                    resp.status_code = 200
                    resp.json = lambda: [{"id": "123456", "owner": False, "permissions": 0}]
                elif url.endswith("/member"):
                    resp.status_code = 200
                    resp.json = lambda: {"roles": ["999777111"]}
                else:
                    resp.status_code = 404
                return resp

            mock_get.side_effect = mock_get_router

            is_admin, reason, guild_id = await DiscordOAuthService.verify_admin_status(
                discord_id="555000",
                access_token="fake_token",
                session=session,
            )

            assert is_admin is True
            assert "SYSTEM" in reason
@pytest.mark.asyncio
async def test_discord_oauth_callback_csrf_missing_cookie(client: AsyncClient):
    """Verifica que si no hay cookie oauth_state (intento de bypass CSRF), se rechaza la solicitud."""
    resp = await client.get(
        "/api/v1/admin/auth/discord/callback?code=some_code&state=some_state",
        follow_redirects=False
    )
    assert resp.status_code == 303
    assert "error=csrf_invalid" in resp.headers["location"]


@pytest.mark.asyncio
async def test_verify_admin_status_via_bot_config_admin_role(session):
    """Verifica que un rol configurado en BotConfig(ADMIN_ROLE_ID) conceda acceso administrativo."""
    from src.connections.databases.db import BotConfig

    cfg = BotConfig(config_key="ADMIN_ROLE_ID", config_value="1433128734826692811")
    session.add(cfg)
    await session.commit()

    with patch.object(DiscordOAuthService, "resolve_guild_id", return_value="777888"):
        with patch("httpx.AsyncClient.get") as mock_get:
            def mock_router(url, *args, **kwargs):
                resp = AsyncMock()
                if url.endswith("/guilds"):
                    resp.status_code = 200
                    resp.json = lambda: [{"id": "777888", "owner": False, "permissions": 0}]
                elif url.endswith("/member"):
                    resp.status_code = 200
                    resp.json = lambda: {"roles": ["1433128734826692811"]}
                else:
                    resp.status_code = 404
                return resp

            mock_get.side_effect = mock_router

            is_admin, reason, guild_id = await DiscordOAuthService.verify_admin_status(
                discord_id="999888777",
                access_token="fake_token",
                session=session,
            )

            assert is_admin is True
            assert "Staff" in reason or "SYSTEM" in reason
            assert guild_id == "777888"


def test_render_dashboard_html_caching():
    """Verifica que render_dashboard_html use caché en memoria en modo producción."""
    from src.modules.v1.routers.admin_dashboard import render_dashboard_html, DASHBOARD_HTML_PATH
    import src.modules.v1.routers.admin_dashboard as mod

    with patch("src.modules.v1.routers.admin_dashboard.is_prod", return_value=True):
        mod._cached_dashboard_html = "<!-- CACHED CONTENT TEST -->"
        content = render_dashboard_html()
        assert content == "<!-- CACHED CONTENT TEST -->"
        # Limpiar
        mod._cached_dashboard_html = None


@pytest.mark.asyncio
async def test_security_headers_on_admin_routes(client: AsyncClient):
    """Verifica que las cabeceras HTTP de seguridad (clickjacking, MIME sniffing) estén presentes."""
    for path in ("/admin", "/admin/", "/api/v1/admin", "/api/v1/admin/"):
        resp = await client.get(path)
        assert resp.status_code == 200
        assert resp.headers.get("X-Frame-Options") == "SAMEORIGIN"
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"


def test_admin_session_token_bearer_case_and_oversize():
    """Verifica que tokens mayores a 4KB sean rechazados y el token se extraiga con Bearer case-insensitive."""
    from unittest.mock import MagicMock
    from src.security.guard import extract_admin_session_token

    # 1. Token oversized (> 4096 caracteres)
    giant_token = "a" * 4097
    assert verify_admin_session_token(giant_token) is None

    # 2. Case-insensitive Bearer
    req = MagicMock()
    req.cookies = {}
    req.headers = {"Authorization": "bearer my_test_token"}
    assert extract_admin_session_token(req) == "my_test_token"

    req_upper = MagicMock()
    req_upper.cookies = {}
    req_upper.headers = {"Authorization": "Bearer my_test_token_2"}
    assert extract_admin_session_token(req_upper) == "my_test_token_2"


@pytest.mark.asyncio
async def test_admin_steam_unlink_lifecycle(client: AsyncClient, session):
    """Verifica el ciclo completo de desvinculación de Steam por parte de un admin."""
    from src.connections.databases.db import Player, BotConfig

    discord_id = "777666555"
    steam_id = "76561198000000888"

    # Preparar Player en BD
    player = Player(steam_id=steam_id, discord_id=discord_id, in_game_name="AdminPlayer")
    session.add(player)
    # Configurar LINK_ROLE_ID y GUILD_ID
    session.add(BotConfig(config_key="LINK_ROLE_ID", config_value="1433128734826692811"))
    session.add(BotConfig(config_key="GUILD_ID", config_value="555444333"))
    await session.commit()

    # 1. Sin sesión -> 401
    resp_unauth = await client.post("/api/v1/admin/auth/steam/unlink")
    assert resp_unauth.status_code == 401

    # 2. Con sesión activa
    token = create_admin_session_token({
        "discord_id": discord_id,
        "username": "AdminUnlinkTester",
        "steam_id": steam_id,
        "steam_name": "AdminPlayer",
        "is_admin": True,
        "guild_id": "555444333",
    })

    with patch("httpx.AsyncClient.delete") as mock_delete:
        mock_resp = AsyncMock()
        mock_resp.status_code = 204
        mock_delete.return_value = mock_resp

        resp = await client.post(
            "/api/v1/admin/auth/steam/unlink",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        res_json = resp.json()
        assert res_json["ok"] is True
        assert "desvinculada exitosamente" in res_json["message"]

        # Verificar que se intentó remover el rol en Discord
        mock_delete.assert_called_once()
        called_url = mock_delete.call_args[0][0]
        assert "1433128734826692811" in called_url
        assert discord_id in called_url

        # Verificar que el Player en BD ahora tiene discord_id == None
        await session.refresh(player)
        assert player.discord_id is None

        # Verificar que la cookie devuelta tiene una nueva sesión sin Steam ID
        set_cookie = resp.headers.get("set-cookie", "")
        assert "admin_session=" in set_cookie


@pytest.mark.asyncio
async def test_admin_steam_callback_identity_fallback(client: AsyncClient, session):
    """Verifica que el callback de Steam soporte 'openid.identity' si 'claimed_id' falta, y acepte HTTP."""
    from src.modules.v1.services.players_service import PlayersService

    admin_data = {
        "discord_id": "888999000",
        "username": "SteamFallbackTester",
        "is_admin": True,
    }
    session_token = create_admin_session_token(admin_data)

    with patch("httpx.AsyncClient.post") as mock_post, \
         patch.object(PlayersService, "link_account", new_callable=AsyncMock) as mock_link:
        
        mock_resp = AsyncMock()
        mock_resp.text = "is_valid:true\n"
        mock_post.return_value = mock_resp

        # Usar openid.identity y scheme http:// con trailing slash
        query = (
            "openid.mode=id_res&"
            "openid.identity=http://steamcommunity.com/openid/id/76561198000000777/"
        )
        resp = await client.get(
            f"/api/v1/admin/auth/steam/callback?{query}",
            headers={"Cookie": f"admin_session={session_token}"},
            follow_redirects=False
        )

        assert resp.status_code == 303
        assert resp.headers["location"] == "/admin"
        mock_link.assert_called_once()
        call_req = mock_link.call_args[0][0]
        assert call_req.steam_id == "76561198000000777"
        assert call_req.discord_id == "888999000"




