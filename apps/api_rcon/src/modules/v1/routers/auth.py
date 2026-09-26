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
from src.modules.v1.services import PlayersService, AuthPageService
from wardogs_schemas.steam_token import verify_steam_link_token

router = APIRouter(prefix="/auth/steam", tags=["Auth"])

DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")

# Aliases para retrocompatibilidad
render_success_page = AuthPageService.render_success_page
render_error_page = AuthPageService.render_error_page
render_html_page = AuthPageService._render_fallback_page


@router.get("/login")
async def steam_login(request: Request, token: str):
    secret_key = ENVIRONMENT_SETTINGS.SECURITY_SETTINGS.API_KEY
    payload = verify_steam_link_token(token, secret_key)
    if not payload:
        html = render_error_page(
            title="Enlace Expirado o Inválido",
            message="El enlace de vinculación ha caducado o no es válido.",
            detail="Por favor, regresa a Discord y vuelve a solicitar la vinculación con el comando /player link."
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
        html = render_error_page(
            title="Enlace Expirado",
            message="El tiempo para completar la vinculación ha expirado.",
            detail="Por favor, solicita un nuevo enlace en Discord con /player link."
        )
        return HTMLResponse(content=html, status_code=400)

    discord_id = payload.get("discord_id")
    guild_id = payload.get("guild_id")

    query_params = dict(request.query_params)
    mode = query_params.get("openid.mode")
    if mode != "id_res":
        html = render_error_page(
            title="Autenticación Cancelada",
            message="Has cancelado el inicio de sesión con Steam.",
            detail="Puedes volver a intentarlo cuando desees desde Discord con /player link."
        )
        return HTMLResponse(content=html, status_code=400)

    # Validar firma OpenID con Steam
    check_params = query_params.copy()
    check_params["openid.mode"] = "check_authentication"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post("https://steamcommunity.com/openid/login", data=check_params)
            if "is_valid:true" not in resp.text:
                html = render_error_page(
                    title="Firma No Válida",
                    message="Steam no pudo verificar la autenticidad de la sesión.",
                    detail="Por favor, intenta nuevamente desde Discord."
                )
                return HTMLResponse(content=html, status_code=400)
    except Exception as e:
        html = render_error_page(
            title="Error al conectar con Steam",
            message=f"No se pudo contactar los servidores de Steam para verificar la firma ({e}).",
            detail="Verifica tu conexión o intenta más tarde."
        )
        return HTMLResponse(content=html, status_code=500)

    # Extraer Steam ID 64
    claimed_id = query_params.get("openid.claimed_id", "")
    match = re.search(r"https://steamcommunity.com/openid/id/(\d+)", claimed_id)
    if not match:
        html = render_error_page(
            title="Steam ID no encontrado",
            message="No se pudo extraer el Steam ID de la respuesta de Steam.",
            detail="La respuesta recibida no contiene un identificador válido."
        )
        return HTMLResponse(content=html, status_code=400)

    steam_id = match.group(1)
    discord_id_str = str(discord_id)

    # Vincular cuenta en la base de datos
    try:
        link_req = LinkAccountRequest(discord_id=discord_id_str, steam_id=steam_id)
        await PlayersService.link_account(link_req, session)
    except HTTPException as ex:
        html = render_error_page(
            title="Error al Vincular",
            message=str(ex.detail),
            detail="Si tu cuenta ya está vinculada a otro usuario, contacta con soporte en Discord."
        )
        return HTMLResponse(content=html, status_code=ex.status_code)

    # Obtener nombre y avatar de Steam
    player_name = None
    avatar_url = None
    profile_url = f"https://steamcommunity.com/profiles/{steam_id}"
    try:
        steam_profile = await get_player_summary(steam_id)
        if steam_profile:
            player_name = steam_profile.get("personaname")
            avatar_url = steam_profile.get("avatarfull")
            if steam_profile.get("profileurl"):
                profile_url = steam_profile.get("profileurl")
            
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

    # Obtener metadatos de Discord desde el payload o Discord REST API
    discord_username = payload.get("discord_username")
    discord_tag = payload.get("discord_tag")
    discord_avatar = payload.get("discord_avatar")

    if DISCORD_TOKEN and (not discord_username or not discord_avatar):
        dc_profile = await AuthPageService.fetch_discord_profile(discord_id_str, DISCORD_TOKEN)
        if not discord_username:
            discord_username = dc_profile["username"]
        if not discord_tag:
            discord_tag = dc_profile["tag"]
        if not discord_avatar and dc_profile["avatar_url"]:
            discord_avatar = dc_profile["avatar_url"]

    if not discord_username:
        discord_username = f"Usuario ({discord_id_str})"
    if not discord_tag:
        discord_tag = f"ID: {discord_id_str}"
    if not discord_avatar:
        discord_avatar = "https://cdn.discordapp.com/embed/avatars/0.png"

    if not player_name:
        existing_p = await session.get(Player, steam_id)
        player_name = existing_p.in_game_name if existing_p and existing_p.in_game_name else f"Steam ({steam_id})"
    if not avatar_url:
        existing_p = await session.get(Player, steam_id)
        avatar_url = existing_p.avatar_url if existing_p and existing_p.avatar_url else "/static/images/steam_icon_black.png"

    # Renderizar pantalla de éxito con templates mejorados y datos reales
    html = render_success_page(
        discord_name=discord_username,
        discord_tag=discord_tag,
        discord_id=discord_id_str,
        discord_avatar=discord_avatar,
        steam_name=player_name,
        steam_id=steam_id,
        steam_avatar=avatar_url,
        steam_profile_url=profile_url
    )
    
    return HTMLResponse(content=html, status_code=200)
