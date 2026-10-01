import os
import re
import secrets
import urllib.parse
import logging
from pathlib import Path
import time
from typing import Dict, Any, Optional, List
from pydantic import BaseModel

import httpx
from fastapi import APIRouter, Request, Depends, HTTPException, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from src.config import ENVIRONMENT_SETTINGS, is_prod
from src.connections.databases.db import get_session, Player, BotConfig
from src.connections.apis.steam import get_player_summary, get_player_summaries
from src.security.guard import (
    create_admin_session_token,
    verify_admin_session_token,
    get_current_admin_session,
    extract_admin_session_token,
)
from src.modules.v1.services.discord_oauth_service import DiscordOAuthService
from src.modules.v1.services.players_service import PlayersService
from src.modules.v1.schemas.dtos import LinkAccountRequest, UnlinkAccountRequest

logger = logging.getLogger("wardogs.admin_dashboard")

router = APIRouter(prefix="/admin", tags=["Admin Dashboard"])

PAGES_ADMIN_DIR = Path(__file__).resolve().parents[4] / "pages" / "admin"
DASHBOARD_HTML_PATH = PAGES_ADMIN_DIR / "index.html"


def _get_proto(request: Request) -> str:
    raw_proto = request.headers.get("x-forwarded-proto")
    if raw_proto:
        first = raw_proto.split(",")[0].strip().lower()
        if first in ("http", "https"):
            return first
    return request.url.scheme.lower()


def _is_secure_request(request: Request) -> bool:
    """Determina si la conexión entrante debe considerarse segura (HTTPS o detrás de proxy inverso)."""
    if _get_proto(request) == "https":
        return True
    return is_prod()


def _get_base_url(request: Request) -> str:
    """Determina la URL base pública de la aplicación, ignorando placeholders de entorno."""
    public_url = ENVIRONMENT_SETTINGS.CONNECTIONS_SETTINGS.PUBLIC_API_URL or os.environ.get("PUBLIC_API_URL")
    if public_url and "<" not in public_url and ">" not in public_url:
        return public_url.strip().rstrip("/")
    proto = _get_proto(request)
    raw_host = request.headers.get("x-forwarded-host")
    if raw_host:
        host = raw_host.split(",")[0].strip()
    else:
        host = request.headers.get("host") or request.url.netloc
    return f"{proto}://{host}".rstrip("/")


def _get_discord_redirect_uri(request: Request) -> str:
    """Retorna la URI de callback de Discord configurada o la autocalcula desde la URL base."""
    configured = ENVIRONMENT_SETTINGS.SECURITY_SETTINGS.DISCORD_REDIRECT_URI or os.environ.get("DISCORD_REDIRECT_URI")
    if configured and "<" not in configured and ">" not in configured:
        return configured.strip()
    return f"{_get_base_url(request)}/api/v1/admin/auth/discord/callback"


def _redirect_with_cookie_cleanup(url: str) -> RedirectResponse:
    """Genera una redirección 303 asegurando que la cookie temporal de OAuth sea eliminada."""
    resp = RedirectResponse(url, status_code=303)
    resp.delete_cookie(key="oauth_state", path="/")
    return resp


_cached_dashboard_html: Optional[str] = None


def render_dashboard_html() -> str:
    """Retorna el contenido de la SPA de administración, utilizando caché en memoria en producción."""
    global _cached_dashboard_html
    if _cached_dashboard_html is not None and is_prod():
        return _cached_dashboard_html

    if not DASHBOARD_HTML_PATH.is_file():
        raise HTTPException(status_code=404, detail="Página del dashboard no encontrada.")
    content = DASHBOARD_HTML_PATH.read_text(encoding="utf-8")
    if is_prod():
        _cached_dashboard_html = content
    return content


def create_admin_html_response() -> HTMLResponse:
    """Genera la respuesta HTML con las cabeceras HTTP de seguridad recomendadas (anti-clickjacking, MIME-sniffing)."""
    response = HTMLResponse(content=render_dashboard_html(), status_code=200)
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def serve_admin_dashboard_v1():
    """Sirve la Single Page Application (SPA) del Dashboard de Administradores con cabeceras de seguridad."""
    return create_admin_html_response()


@router.get("/auth/discord/login")
async def discord_login(request: Request):
    """Inicia el flujo de autenticación de Discord OAuth2 con protección CSRF."""
    redirect_uri = _get_discord_redirect_uri(request)
    state = secrets.token_urlsafe(16)
    try:
        auth_url = DiscordOAuthService.get_authorization_url(redirect_uri=redirect_uri, state=state)
    except ValueError as e:
        logger.error("Error al generar URL de Discord OAuth: %s", e)
        return RedirectResponse(f"/admin?error=config_missing&msg={urllib.parse.quote(str(e))}", status_code=303)

    resp = RedirectResponse(auth_url, status_code=303)
    resp.set_cookie(
        key="oauth_state",
        value=state,
        max_age=600,
        httponly=True,
        samesite="lax",
        secure=_is_secure_request(request),
        path="/",
    )
    return resp


@router.get("/auth/discord/callback")
async def discord_callback(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    error_description: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
):
    """Callback de Discord OAuth2 que valida estado CSRF y permisos de administrador."""
    saved_state = request.cookies.get("oauth_state")
    if not saved_state or not state or not secrets.compare_digest(saved_state, state):
        logger.warning(
            "Fallo en la verificación de state CSRF en Discord OAuth (saved=%s, received=%s)",
            bool(saved_state),
            bool(state),
        )
        return _redirect_with_cookie_cleanup("/admin?error=csrf_invalid&msg=Fallo+de+seguridad+OAuth+(CSRF)")

    if error or not code:
        err_msg = error_description or error or "Autorización cancelada"
        logger.warning("Error en retorno de Discord OAuth: %s", err_msg)
        return _redirect_with_cookie_cleanup(f"/admin?error=oauth_denied&msg={urllib.parse.quote(err_msg)}")

    redirect_uri = _get_discord_redirect_uri(request)

    try:
        tokens = await DiscordOAuthService.exchange_code_for_token(code, redirect_uri)
        access_token = tokens["access_token"]
        user_profile = await DiscordOAuthService.fetch_user_profile(access_token)
    except Exception as ex:
        logger.error("Fallo durante el intercambio de token con Discord: %s", ex, exc_info=True)
        return _redirect_with_cookie_cleanup(f"/admin?error=token_exchange&msg={urllib.parse.quote(str(ex))}")

    discord_id = user_profile["id"]

    # Verificar si el usuario es Administrador o tiene rol SYSTEM
    is_admin, reason, guild_id = await DiscordOAuthService.verify_admin_status(
        discord_id=discord_id,
        access_token=access_token,
        session=session,
    )

    if not is_admin:
        logger.warning("Intento de acceso rechazado a Discord ID %s: %s", discord_id, reason)
        return _redirect_with_cookie_cleanup(
            f"/admin?error=unauthorized&msg={urllib.parse.quote(f'Acceso denegado: {reason}')}"
        )


    # Comprobar si ya tiene Steam ID vinculado en DB
    steam_id, steam_name, steam_avatar = await DiscordOAuthService.get_linked_steam_id(discord_id, session)

    session_payload = {
        "discord_id": discord_id,
        "username": user_profile["username"],
        "avatar_url": user_profile["avatar_url"],
        "steam_id": steam_id,
        "steam_name": steam_name,
        "steam_avatar": steam_avatar,
        "is_admin": True,
        "auth_reason": reason,
        "guild_id": guild_id,
    }

    session_token = create_admin_session_token(session_payload)

    response = RedirectResponse("/admin", status_code=303)
    response.set_cookie(
        key="admin_session",
        value=session_token,
        max_age=604800,  # 7 días
        httponly=True,
        samesite="lax",
        secure=_is_secure_request(request),
        path="/",
    )
    # Limpiar cookie temporal de estado
    response.delete_cookie(key="oauth_state", path="/")
    logger.info("Sesión de administrador iniciada para %s (%s)", user_profile['username'], discord_id)
    return response


@router.get("/auth/me")
async def get_current_admin(session_data: Dict[str, Any] = Depends(get_current_admin_session)):
    """Devuelve los datos del perfil y permisos de la sesión administrativa actual."""
    return {"authenticated": True, "admin": session_data}


@router.post("/auth/logout")
async def admin_logout(response: Response):
    """Cierra la sesión del administrador eliminando la cookie."""
    response.delete_cookie(key="admin_session", path="/")
    return {"ok": True, "message": "Sesión cerrada correctamente"}


# ====================================================================
# Steam OAuth para Administradores (OpenID 2.0)
# ====================================================================

@router.get("/auth/steam/link")
async def admin_steam_link(request: Request, session_data: Dict[str, Any] = Depends(get_current_admin_session)):
    """Inicia el flujo de OpenID con Steam para vincular cuenta al administrador autenticado."""
    base_url = _get_base_url(request)
    return_to = f"{base_url}/api/v1/admin/auth/steam/callback"
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


async def _sync_discord_link_role(
    discord_id: str,
    guild_id: Optional[str],
    session: AsyncSession,
    assign: bool = True,
) -> None:
    """Asigna o remueve el rol de vinculación LINK_ROLE_ID en Discord."""
    bot_token = ENVIRONMENT_SETTINGS.SECURITY_SETTINGS.DISCORD_TOKEN or os.environ.get("DISCORD_TOKEN")
    if not bot_token:
        return
    resolved_guild = guild_id or await DiscordOAuthService.resolve_guild_id(session)
    if not resolved_guild:
        return
    try:
        cfg_link = await session.get(BotConfig, "LINK_ROLE_ID")
        if not (cfg_link and cfg_link.config_value and cfg_link.config_value.strip().isdigit()):
            return
        target_role = cfg_link.config_value.strip()
        reason = "Rol de vinculacion asignado via Admin Dashboard" if assign else "Rol de vinculacion removido via Admin Dashboard"
        headers = {
            "Authorization": f"Bot {bot_token}",
            "X-Audit-Log-Reason": urllib.parse.quote(reason),
        }
        role_url = f"https://discord.com/api/v10/guilds/{resolved_guild}/members/{discord_id}/roles/{target_role}"
        async with httpx.AsyncClient(timeout=5.0) as discord_client:
            if assign:
                await discord_client.put(role_url, headers=headers)
            else:
                await discord_client.delete(role_url, headers=headers)
    except Exception as discord_err:
        logger.debug("Omitiendo sincronización de rol LINK_ROLE_ID en Discord (%s): %s", "assign" if assign else "remove", discord_err)


@router.get("/auth/steam/callback")
async def admin_steam_callback(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Valida la firma OpenID de Steam y actualiza la sesión y base de datos del administrador."""
    session_token = extract_admin_session_token(request)
    session_data = verify_admin_session_token(session_token) if session_token else None
    if not session_data or not session_data.get("is_admin"):
        return RedirectResponse("/admin?error=session_expired&msg=Inicia+sesion+nuevamente", status_code=303)

    query_params = dict(request.query_params)
    mode = query_params.get("openid.mode")
    if mode != "id_res":
        return RedirectResponse("/admin?error=steam_cancelled", status_code=303)

    # Validar firma con Steam
    check_params = query_params.copy()
    check_params["openid.mode"] = "check_authentication"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post("https://steamcommunity.com/openid/login", data=check_params)
            if "is_valid:true" not in resp.text:
                return RedirectResponse("/admin?error=steam_invalid_sig", status_code=303)
    except Exception as e:
        logger.error("Error al verificar firma con servidores Steam: %s", e)
        return RedirectResponse(f"/admin?error=steam_network_err&msg={urllib.parse.quote(str(e))}", status_code=303)

    # Extraer Steam ID 64
    claimed_id = query_params.get("openid.claimed_id") or query_params.get("openid.identity") or ""
    match = re.search(r"https?://steamcommunity.com/openid/id/(\d+)", claimed_id)
    if not match:
        return RedirectResponse("/admin?error=steam_id_missing", status_code=303)

    steam_id = match.group(1)

    # Obtener nombre y avatar de Steam
    steam_name = f"Steam ({steam_id})"
    steam_avatar = "/static/images/steam_icon_black.png"
    try:
        profile = await get_player_summary(steam_id)
        if profile:
            steam_name = profile.get("personaname") or steam_name
            steam_avatar = profile.get("avatarfull") or steam_avatar
    except Exception:
        pass

    # Sincronizar vinculación en la base de datos oficial
    discord_id = session_data.get("discord_id")
    if discord_id:
        try:
            link_req = LinkAccountRequest(discord_id=str(discord_id), steam_id=steam_id)
            await PlayersService.link_account(link_req, session)

            # Actualizar datos de jugador si se resolvió el perfil
            player = await session.get(Player, steam_id)
            if player:
                if steam_name and not steam_name.startswith("Steam ("):
                    player.in_game_name = steam_name
                if steam_avatar and steam_avatar.startswith("http"):
                    player.avatar_url = steam_avatar
                session.add(player)
                await session.commit()

            # Sincronizar rol de vinculación en Discord si está configurado
            await _sync_discord_link_role(
                discord_id=str(discord_id),
                guild_id=session_data.get("guild_id"),
                session=session,
                assign=True,
            )
        except HTTPException as he:
            logger.warning("Conflicto al vincular cuenta Steam para admin %s: %s", discord_id, he.detail)
            return RedirectResponse(
                f"/admin?error=steam_conflict&msg={urllib.parse.quote(str(he.detail))}",
                status_code=303
            )
        except Exception as e:
            logger.error("Error al actualizar Player en DB tras Steam OAuth: %s", e, exc_info=True)
            return RedirectResponse(
                f"/admin?error=steam_db_error&msg={urllib.parse.quote('Error al registrar vinculación en base de datos')}",
                status_code=303
            )

    # Actualizar datos en sesión del admin
    session_data["steam_id"] = steam_id
    session_data["steam_name"] = steam_name
    session_data["steam_avatar"] = steam_avatar

    new_token = create_admin_session_token(session_data)

    response = RedirectResponse("/admin", status_code=303)
    response.set_cookie(
        key="admin_session",
        value=new_token,
        max_age=604800,
        httponly=True,
        samesite="lax",
        secure=_is_secure_request(request),
        path="/",
    )
    logger.info("Admin %s vinculo Steam ID %s en el dashboard", session_data.get('username'), steam_id)
    return response


@router.post("/auth/steam/unlink")
async def admin_steam_unlink(
    request: Request,
    response: Response,
    session_data: Dict[str, Any] = Depends(get_current_admin_session),
    session: AsyncSession = Depends(get_session),
):
    """Desvincula la cuenta de Steam del administrador autenticado tanto en DB como en la sesión."""
    discord_id = session_data.get("discord_id")
    if not discord_id:
        raise HTTPException(status_code=400, detail="Discord ID faltante en sesión")

    # 1. Desvincular en base de datos
    try:
        unlink_req = UnlinkAccountRequest(discord_id=str(discord_id))
        await PlayersService.unlink_account(unlink_req, session)
    except HTTPException:
        pass

    # 2. Sincronizar remoción del rol LINK_ROLE_ID en Discord si correspondía
    await _sync_discord_link_role(
        discord_id=str(discord_id),
        guild_id=session_data.get("guild_id"),
        session=session,
        assign=False,
    )

    # 3. Actualizar sesión del admin
    session_data["steam_id"] = None
    session_data["steam_name"] = None
    session_data["steam_avatar"] = None

    new_token = create_admin_session_token(session_data)
    response.set_cookie(
        key="admin_session",
        value=new_token,
        max_age=604800,
        httponly=True,
        samesite="lax",
        secure=_is_secure_request(request),
        path="/",
    )
    logger.info("Admin %s desvinculó su cuenta de Steam", session_data.get("username"))
    return {"ok": True, "message": "Cuenta de Steam desvinculada exitosamente"}


_DISCORD_CACHE: Dict[str, Any] = {
    "roles": None,
    "roles_time": 0,
    "channels": None,
    "channels_time": 0,
    "users": {},
}


@router.get("/discord/roles")
async def get_discord_roles(
    session_data: Dict[str, Any] = Depends(get_current_admin_session),
    session: AsyncSession = Depends(get_session),
):
    """Retorna la lista de roles del servidor de Discord con sus nombres, colores e IDs."""
    now = time.time()
    if _DISCORD_CACHE["roles"] is not None and (now - _DISCORD_CACHE["roles_time"]) < 60:
        return _DISCORD_CACHE["roles"]

    guild_id = session_data.get("guild_id") or await DiscordOAuthService.resolve_guild_id(session)
    bot_token = ENVIRONMENT_SETTINGS.SECURITY_SETTINGS.DISCORD_TOKEN or os.environ.get("DISCORD_TOKEN")
    if not guild_id or not bot_token:
        return []

    headers = {
        "Authorization": f"Bot {bot_token}",
        "User-Agent": "DiscordBot (https://matefield.com, 1.0)",
    }
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(f"https://discord.com/api/v10/guilds/{guild_id}/roles", headers=headers)
            if resp.status_code == 200:
                raw_roles = resp.json()
                result = []
                for r in raw_roles:
                    color_int = r.get("color", 0)
                    hex_color = f"#{color_int:06x}" if color_int else "#99aab5"
                    result.append({
                        "id": str(r["id"]),
                        "name": r.get("name", "Rol"),
                        "color": hex_color,
                        "position": r.get("position", 0),
                    })
                result.sort(key=lambda x: x["position"], reverse=True)
                _DISCORD_CACHE["roles"] = result
                _DISCORD_CACHE["roles_time"] = now
                return result
    except Exception as e:
        logger.error("Error al obtener roles de Discord: %s", e)

    return _DISCORD_CACHE["roles"] or []


@router.get("/discord/channels")
async def get_discord_channels(
    session_data: Dict[str, Any] = Depends(get_current_admin_session),
    session: AsyncSession = Depends(get_session),
):
    """Retorna canales de texto y anuncios de Discord para configuración."""
    now = time.time()
    if _DISCORD_CACHE["channels"] is not None and (now - _DISCORD_CACHE["channels_time"]) < 60:
        return _DISCORD_CACHE["channels"]

    guild_id = session_data.get("guild_id") or await DiscordOAuthService.resolve_guild_id(session)
    bot_token = ENVIRONMENT_SETTINGS.SECURITY_SETTINGS.DISCORD_TOKEN or os.environ.get("DISCORD_TOKEN")
    if not guild_id or not bot_token:
        return []

    headers = {
        "Authorization": f"Bot {bot_token}",
        "User-Agent": "DiscordBot (https://matefield.com, 1.0)",
    }
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(f"https://discord.com/api/v10/guilds/{guild_id}/channels", headers=headers)
            if resp.status_code == 200:
                raw_channels = resp.json()
                result = [
                    {"id": str(c["id"]), "name": c.get("name", "canal")}
                    for c in raw_channels
                    if c.get("type") in (0, 5)  # GUILD_TEXT o GUILD_ANNOUNCEMENT
                ]
                result.sort(key=lambda x: x["name"])
                _DISCORD_CACHE["channels"] = result
                _DISCORD_CACHE["channels_time"] = now
                return result
    except Exception as e:
        logger.error("Error al obtener canales de Discord: %s", e)

    return _DISCORD_CACHE["channels"] or []


class IdentityResolveRequest(BaseModel):
    steam_ids: List[str] = []
    discord_ids: List[str] = []


@router.post("/identities/resolve")
async def resolve_identities(
    req: IdentityResolveRequest,
    session_data: Dict[str, Any] = Depends(get_current_admin_session),
    session: AsyncSession = Depends(get_session),
):
    """Resuelve nombres y avatares para IDs de Steam y Discord."""
    bot_token = ENVIRONMENT_SETTINGS.SECURITY_SETTINGS.DISCORD_TOKEN or os.environ.get("DISCORD_TOKEN")
    resolved_steam: Dict[str, Dict[str, Any]] = {}
    resolved_discord: Dict[str, Dict[str, Any]] = {}

    # 1. Resolver Steam IDs
    clean_steam = [s.strip() for s in req.steam_ids if s.strip()]
    if clean_steam:
        from sqlmodel import col, select
        players = (await session.exec(select(Player).where(col(Player.steam_id).in_(clean_steam)))).all()
        missing_steam = []
        for p in players:
            if p.in_game_name or p.avatar_url:
                resolved_steam[p.steam_id] = {
                    "name": p.in_game_name or f"Steam ({p.steam_id[:6]}...)",
                    "avatar": p.avatar_url or "https://avatars.steamstatic.com/fef49e7fa7e1997310d705b2a6158ff8dc1cdfeb_full.jpg",
                    "discord_id": p.discord_id,
                }
            else:
                missing_steam.append(p.steam_id)

        unregistered = set(clean_steam) - set(resolved_steam.keys())
        missing_steam.extend(list(unregistered))

        if missing_steam:
            try:
                summaries = await get_player_summaries(missing_steam[:100])
                for sid, data in summaries.items():
                    resolved_steam[sid] = {
                        "name": data.get("personaname") or f"Steam ({sid[:6]}...)",
                        "avatar": data.get("avatarfull") or "https://avatars.steamstatic.com/fef49e7fa7e1997310d705b2a6158ff8dc1cdfeb_full.jpg",
                        "discord_id": None,
                    }
            except Exception as e:
                logger.warning("Error resolviendo summaries en Steam: %s", e)

    # 2. Resolver Discord IDs
    clean_discord = [d.strip() for d in req.discord_ids if d.strip()]
    if clean_discord and bot_token:
        headers = {
            "Authorization": f"Bot {bot_token}",
            "User-Agent": "DiscordBot (https://matefield.com, 1.0)",
        }
        async with httpx.AsyncClient(timeout=5.0) as client:
            for did in clean_discord[:50]:
                if did in _DISCORD_CACHE["users"]:
                    resolved_discord[did] = _DISCORD_CACHE["users"][did]
                    continue
                try:
                    resp = await client.get(f"https://discord.com/api/v10/users/{did}", headers=headers)
                    if resp.status_code == 200:
                        udata = resp.json()
                        avatar_hash = udata.get("avatar")
                        if avatar_hash:
                            ext = "gif" if avatar_hash.startswith("a_") else "png"
                            av_url = f"https://cdn.discordapp.com/avatars/{did}/{avatar_hash}.{ext}"
                        else:
                            av_url = "https://cdn.discordapp.com/embed/avatars/0.png"
                        u_info = {
                            "username": udata.get("username", did),
                            "global_name": udata.get("global_name") or udata.get("username", did),
                            "avatar": av_url,
                        }
                        _DISCORD_CACHE["users"][did] = u_info
                        resolved_discord[did] = u_info
                except Exception:
                    pass

    return {
        "steam": resolved_steam,
        "discord": resolved_discord,
    }

