import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from src.modules.v1.services.auth_page_service import AuthPageService


def test_auth_page_service_render_success():
    html = AuthPageService.render_success_page(
        discord_name="Comandante",
        discord_tag="#0001",
        discord_id="111222333444",
        discord_avatar="https://discordcdn.test/avatar.png",
        steam_name="Soldado_Mate",
        steam_id="76561198000000123",
        steam_avatar="https://steamcdn.test/soldado.jpg",
        steam_profile_url="https://steamcommunity.com/profiles/76561198000000123"
    )
    assert "Comandante" in html
    assert "#0001" in html
    assert "111222333444" in html
    assert "Soldado_Mate" in html
    assert "76561198000000123" in html
    assert "BANNER_ICONO_SERVIDOR.png" in html
    assert "BANNER_FONDO_INVITACION.png" in html


def test_auth_page_service_render_error():
    html = AuthPageService.render_error_page(
        title="Firma No Válida",
        message="Steam rechazó la firma OpenID.",
        detail="Intente nuevamente desde Discord."
    )
    assert "Firma No Válida" in html
    assert "Steam rechazó la firma OpenID." in html
    assert "Intente nuevamente desde Discord." in html
    assert "BANNER_ICONO_SERVIDOR.png" in html


@pytest.mark.asyncio
async def test_auth_page_service_fetch_discord_profile():
    # 1. No token provided
    res_none = await AuthPageService.fetch_discord_profile("12345", None)
    assert res_none["username"] is None

    # 2. Valid response
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "username": "mateo",
        "global_name": "Mateo Global",
        "discriminator": "0",
        "avatar": "abcdef123456"
    }

    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_resp)):
        res = await AuthPageService.fetch_discord_profile("12345", "mock_bot_token")
        assert res["username"] == "Mateo Global"
        assert res["tag"] == "@mateo"
        assert res["avatar_url"] is not None and "abcdef123456.png" in res["avatar_url"]


def test_auth_page_service_xss_escaping():
    malicious_name = '<script>alert("xss")</script>'
    malicious_msg = 'Error" onfocus="alert(1)'
    
    success_html = AuthPageService.render_success_page(
        steam_name=malicious_name,
        discord_name='User<foo>'
    )
    assert malicious_name not in success_html
    assert "&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;" in success_html
    assert "<foo>" not in success_html
    assert "&lt;foo&gt;" in success_html

    error_html = AuthPageService.render_error_page(
        title="Error",
        message=malicious_msg,
        detail='<img src=x onerror=alert(2)>'
    )
    assert '<img src=x' not in error_html
    assert "&lt;img src=x onerror=alert(2)&gt;" in error_html


def test_auth_page_service_missing_template_raises():
    from pathlib import Path
    with patch("src.modules.v1.services.auth_page_service.SUCCESS_TEMPLATE_PATH", Path("/nonexistent/success.html")):
        with pytest.raises(FileNotFoundError) as exc_info:
            AuthPageService.render_success_page()
        assert "no encontrada" in str(exc_info.value)

