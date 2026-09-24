import os
import re
import urllib.parse
from typing import Optional
import httpx
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.config import ENVIRONMENT_SETTINGS
from src.connections.databases.db import get_session, Player, BotConfig, Ban
from src.connections.apis.steam import get_player_summary
from src.modules.v1.schemas.dtos import LinkAccountRequest
from src.modules.v1.services.players_service import PlayersService
from wardogs_schemas.steam_token import verify_steam_link_token

router = APIRouter(prefix="/auth/steam", tags=["Auth"])

DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")

def render_html_page(title: str, content: str, is_success: bool = True) -> str:
    badge_bg = "#059669" if is_success else "#dc2626"
    badge_icon = "✓" if is_success else "✕"
    badge_text = "VINCULACIÓN EXITOSA" if is_success else "ERROR DE VINCULACIÓN"
    
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} | Matefield</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            background: #0b0f19;
            color: #f1f5f9;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            padding: 20px;
        }}
        .card {{
            background: #151d2f;
            border: 1px solid #23304c;
            border-radius: 20px;
            padding: 36px 30px;
            max-width: 460px;
            width: 100%;
            text-align: center;
            box-shadow: 0 20px 40px -15px rgba(0, 0, 0, 0.7);
        }}
        .badge {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            background: {badge_bg};
            color: #ffffff;
            font-weight: 700;
            font-size: 0.85rem;
            letter-spacing: 0.05em;
            padding: 6px 16px;
            border-radius: 9999px;
            margin-bottom: 24px;
        }}
        .avatar-wrap {{
            margin: 0 auto 20px auto;
            width: 90px;
            height: 90px;
            position: relative;
        }}
        .avatar {{
            width: 90px;
            height: 90px;
            border-radius: 50%;
            border: 3px solid #38bdf8;
            object-fit: cover;
            box-shadow: 0 0 20px rgba(56, 189, 248, 0.3);
        }}
        h1 {{
            font-size: 1.5rem;
            font-weight: 700;
            margin-bottom: 12px;
            color: #ffffff;
        }}
        p {{
            color: #94a3b8;
            font-size: 0.95rem;
            line-height: 1.5;
            margin-bottom: 24px;
        }}
        .details {{
            background: #0d1322;
            border: 1px solid #1c273e;
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 24px;
            text-align: left;
            font-size: 0.9rem;
        }}
        .details-row {{
            display: flex;
            justify-content: space-between;
            padding: 6px 0;
            border-bottom: 1px solid #1c273e;
        }}
        .details-row:last-child {{
            border-bottom: none;
        }}
        .details-label {{
            color: #64748b;
        }}
        .details-val {{
            color: #e2e8f0;
            font-weight: 600;
            font-family: monospace;
        }}
        .footer-note {{
            font-size: 0.82rem;
            color: #64748b;
        }}
    </style>
</head>
<body>
    <div class="card">
        <div class="badge"><span>{badge_icon}</span> {badge_text}</div>
        {content}
        <div class="footer-note">Puedes cerrar esta ventana de forma segura.</div>
    </div>
</body>
</html>"""


@router.get("/login")
async def steam_login(request: Request, token: str):
    secret_key = ENVIRONMENT_SETTINGS.SECURITY_SETTINGS.API_KEY
    payload = verify_steam_link_token(token, secret_key)
    if not payload:
        html = render_html_page(
            "Enlace Inválido",
            "<h1>Enlace Expirado o Inválido</h1><p>El enlace de vinculación ha caducado o no es válido. Por favor, regresa a Discord y vuelve a solicitar la vinculación con el comando <code>/player link</code>.</p>",
            is_success=False
        )
        return HTMLResponse(content=html, status_code=400)

    # Construir retorno OpenID
    base_url = ENVIRONMENT_SETTINGS.CONNECTIONS_SETTINGS.PUBLIC_API_URL
    if not base_url:
        base_url = str(request.base_url).rstrip("/")
    base_url = base_url.rstrip("/")

    return_to = f"{base_url}/api/v1/auth/steam/callback?token={token}"
    realm = f"{base_url}/"

    params = {
        "openid.ns": "http://specs.openid.net/auth/2.0",
        "openid.mode": "checkid_setup",
        "openid.return_to": return_to,
        "openid.realm": realm,
        "openid.identity": "http://specs.openid.net/auth/2.0/identifier_select",
        "openid.claimed_id": "http://specs.openid.net/auth/2.0/identifier_select",
    }
    
    steam_auth_url = f"https://steamcommunity.com/openid/login?{urllib.parse.urlencode(params)}"
    return RedirectResponse(steam_auth_url, status_code=303)


@router.get("/callback")
async def steam_callback(request: Request, token: str, session: AsyncSession = Depends(get_session)):
    secret_key = ENVIRONMENT_SETTINGS.SECURITY_SETTINGS.API_KEY
    payload = verify_steam_link_token(token, secret_key)
    if not payload:
        html = render_html_page(
            "Enlace Expirado",
            "<h1>Sesión Expirada</h1><p>El tiempo para completar la vinculación ha expirado. Por favor, solicita un nuevo enlace en Discord con <code>/player link</code>.</p>",
            is_success=False
        )
        return HTMLResponse(content=html, status_code=400)

    discord_id = payload.get("discord_id")
    guild_id = payload.get("guild_id")

    query_params = dict(request.query_params)
    mode = query_params.get("openid.mode")
    if mode != "id_res":
        html = render_html_page(
            "Cancelado",
            "<h1>Autenticación Cancelada</h1><p>Has cancelado el inicio de sesión con Steam. Puedes volver a intentarlo cuando desees desde Discord.</p>",
            is_success=False
        )
        return HTMLResponse(content=html, status_code=400)

    # Validar firma OpenID con Steam
    check_params = query_params.copy()
    check_params["openid.mode"] = "check_authentication"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post("https://steamcommunity.com/openid/login", data=check_params)
            if "is_valid:true" not in resp.text:
                html = render_html_page(
                    "Error de Validación",
                    "<h1>Firma No Válida</h1><p>Steam no pudo verificar la autenticidad de la sesión. Por favor, intenta nuevamente.</p>",
                    is_success=False
                )
                return HTMLResponse(content=html, status_code=400)
    except Exception as e:
        html = render_html_page(
            "Error de Conexión",
            f"<h1>Error al conectar con Steam</h1><p>No se pudo contactar los servidores de Steam para verificar la firma ({e}).</p>",
            is_success=False
        )
        return HTMLResponse(content=html, status_code=500)

    # Extraer Steam ID 64
    claimed_id = query_params.get("openid.claimed_id", "")
    match = re.search(r"https://steamcommunity.com/openid/id/(\d+)", claimed_id)
    if not match:
        html = render_html_page(
            "Error de Steam ID",
            "<h1>Steam ID no encontrado</h1><p>No se pudo extraer el Steam ID de la respuesta de Steam.</p>",
            is_success=False
        )
        return HTMLResponse(content=html, status_code=400)

    steam_id = match.group(1)

    discord_id_str = str(discord_id)
    # Vincular cuenta en la base de datos
    try:
        link_req = LinkAccountRequest(discord_id=discord_id_str, steam_id=steam_id)
        await PlayersService.link_account(link_req, session)
    except HTTPException as ex:
        html = render_html_page(
            "Error al Vincular",
            f"<h1>No se pudo vincular</h1><p>{ex.detail}</p>",
            is_success=False
        )
        return HTMLResponse(content=html, status_code=400)

    # Obtener nombre y avatar de Steam
    player_name = None
    avatar_url = None
    try:
        steam_profile = await get_player_summary(steam_id)
        if steam_profile:
            player_name = steam_profile.get("personaname")
            avatar_url = steam_profile.get("avatarfull")
            
            player = await session.get(Player, steam_id)
            if player:
                if player_name:
                    player.in_game_name = player_name
                if avatar_url:
                    player.avatar_url = avatar_url
                session.add(player)
                await session.commit()
    except Exception:
        pass

    # Asignar roles en Discord de forma inmediata si se dispone de DISCORD_TOKEN y guild_id
    if DISCORD_TOKEN and guild_id:
        try:
            # Consultar si el Steam ID tiene bans activos
            active_ban = (await session.exec(
                select(Ban).where(Ban.steam_id == steam_id, Ban.is_active == True)
            )).first()

            cfg_link = (await session.get(BotConfig, "LINK_ROLE_ID"))
            cfg_ban = (await session.get(BotConfig, "BAN_ROLE_DEFAULT"))
            cfg_unset_ban = (await session.get(BotConfig, "BAN_UNSET_ROLE_ID"))

            async with httpx.AsyncClient(timeout=5.0) as discord_client:
                headers = {"Authorization": f"Bot {DISCORD_TOKEN}"}
                
                if active_ban and cfg_ban and cfg_ban.config_value.isdigit():
                    # Asignar rol de ban
                    await discord_client.put(
                        f"https://discord.com/api/v10/guilds/{guild_id}/members/{discord_id}/roles/{cfg_ban.config_value}",
                        headers=headers
                    )
                    # Quitar rol de unset_ban si aplica
                    if cfg_unset_ban and cfg_unset_ban.config_value.isdigit():
                        await discord_client.delete(
                            f"https://discord.com/api/v10/guilds/{guild_id}/members/{discord_id}/roles/{cfg_unset_ban.config_value}",
                            headers=headers
                        )
                elif cfg_link and cfg_link.config_value.isdigit():
                    # Asignar rol verificado
                    await discord_client.put(
                        f"https://discord.com/api/v10/guilds/{guild_id}/members/{discord_id}/roles/{cfg_link.config_value}",
                        headers=headers
                    )
        except Exception:
            pass

    # Renderizar pantalla de éxito
    avatar_html = f'<div class="avatar-wrap"><img src="{avatar_url}" class="avatar" alt="Steam Avatar" /></div>' if avatar_url else ''
    display_name = player_name or "Jugador"
    
    content = f"""
        {avatar_html}
        <h1>¡Bienvenido, {display_name}!</h1>
        <p>Tu cuenta oficial de Steam ha sido autenticada y vinculada exitosamente con tu usuario de Discord.</p>
        <div class="details">
            <div class="details-row">
                <span class="details-label">Nombre en Steam:</span>
                <span class="details-val">{display_name}</span>
            </div>
            <div class="details-row">
                <span class="details-label">Steam ID 64:</span>
                <span class="details-val">{steam_id}</span>
            </div>
            <div class="details-row">
                <span class="details-label">ID de Discord:</span>
                <span class="details-val">{discord_id}</span>
            </div>
        </div>
    """
    
    return HTMLResponse(content=render_html_page("¡Cuenta Vinculada!", content, is_success=True))
