from pathlib import Path
from typing import Optional, Dict, Any
import httpx
import logging

logger = logging.getLogger("wardogs.auth_pages")

PAGES_DIR = Path(__file__).resolve().parents[4] / "pages" / "steam"
SUCCESS_TEMPLATE_PATH = PAGES_DIR / "success_callback.html"
ERROR_TEMPLATE_PATH = PAGES_DIR / "error_callback.html"


class AuthPageService:
    """
    Servicio desacoplado para la resolución de perfiles y renderizado
    de las interfaces de callback de autenticación Steam OpenID.
    """

    @classmethod
    async def fetch_discord_profile(
        cls, discord_id: str, discord_token: Optional[str]
    ) -> Dict[str, Optional[str]]:
        """
        Consulta la API REST de Discord para obtener nombre de usuario,
        discriminador/tag y avatar si no vienen provistos en el token firmado.
        """
        result = {
            "username": None,
            "tag": None,
            "avatar_url": None,
        }
        if not discord_token or not discord_id:
            return result

        try:
            async with httpx.AsyncClient(timeout=4.0) as dc:
                res = await dc.get(
                    f"https://discord.com/api/v10/users/{discord_id}",
                    headers={"Authorization": f"Bot {discord_token}"},
                )
                if res.status_code == 200:
                    udata = res.json()
                    result["username"] = udata.get("global_name") or udata.get("username")
                    disc = udata.get("discriminator", "0")
                    result["tag"] = f"#{disc}" if disc != "0" else f"@{udata.get('username')}"
                    av_hash = udata.get("avatar")
                    if av_hash:
                        result["avatar_url"] = f"https://cdn.discordapp.com/avatars/{discord_id}/{av_hash}.png"
        except Exception as ex:
            logger.debug(f"No se pudo resolver el perfil de Discord para {discord_id}: {ex}")

        return result

    @classmethod
    def render_success_page(
        cls,
        discord_name: Optional[str] = "",
        discord_tag: Optional[str] = "",
        discord_id: Optional[str] = "",
        discord_avatar: Optional[str] = "",
        steam_name: Optional[str] = "",
        steam_id: Optional[str] = "",
        steam_avatar: Optional[str] = "",
        steam_profile_url: Optional[str] = "",
    ) -> str:
        """Renderiza success_callback.html inyectando datos de usuario y branding de Matefield."""
        discord_name_val = discord_name or "Usuario"
        discord_tag_val = discord_tag or ""
        discord_id_val = discord_id or ""
        discord_avatar_val = discord_avatar or "https://cdn.discordapp.com/embed/avatars/0.png"
        steam_name_val = steam_name or "Jugador"
        steam_id_val = steam_id or ""
        steam_avatar_val = steam_avatar or "/static/images/steam_icon_black.png"
        steam_profile_val = steam_profile_url or (
            f"https://steamcommunity.com/profiles/{steam_id}" if steam_id else "#"
        )

        if SUCCESS_TEMPLATE_PATH.exists():
            content = SUCCESS_TEMPLATE_PATH.read_text(encoding="utf-8")
            replacements = {
                "{{DISCORD_NAME}}": discord_name_val,
                "{{DISCORD_TAG}}": discord_tag_val,
                "{{DISCORD_ID}}": discord_id_val,
                "{{DISCORD_AVATAR}}": discord_avatar_val,
                "{{STEAM_NAME}}": steam_name_val,
                "{{STEAM_ID}}": steam_id_val,
                "{{STEAM_AVATAR}}": steam_avatar_val,
                "{{STEAM_PROFILE_URL}}": steam_profile_val,
            }
            for placeholder, val in replacements.items():
                content = content.replace(placeholder, str(val))
            return content

        # Fallback de seguridad
        return cls._render_fallback_page(
            title="¡Cuenta Vinculada!",
            content=f"""
                <h1>¡Bienvenido, {steam_name_val}!</h1>
                <p>Tu cuenta oficial de Steam ha sido vinculada exitosamente con tu usuario de Discord.</p>
                <p>Steam ID: <strong>{steam_id_val}</strong> | Discord ID: <strong>{discord_id_val}</strong></p>
            """,
            is_success=True,
        )

    @classmethod
    def render_error_page(
        cls,
        title: str,
        message: str,
        detail: Optional[str] = "",
    ) -> str:
        """Renderiza error_callback.html inyectando el motivo de error dinámico."""
        detail_val = detail or ""
        if ERROR_TEMPLATE_PATH.exists():
            content = ERROR_TEMPLATE_PATH.read_text(encoding="utf-8")
            replacements = {
                "{{ERROR_TITLE}}": title,
                "{{ERROR_MESSAGE}}": message,
                "{{ERROR_DETAIL}}": detail_val,
            }
            for placeholder, val in replacements.items():
                content = content.replace(placeholder, str(val))
            return content

        # Fallback de seguridad
        return cls._render_fallback_page(
            title=title,
            content=f"""
                <h1>{title}</h1>
                <p>{message}</p>
                <p style="font-size:0.85rem; color:#ef4444;">{detail_val}</p>
            """,
            is_success=False,
        )

    @staticmethod
    def _render_fallback_page(title: str, content: str, is_success: bool = True) -> str:
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
            background: #07090c;
            color: #f1f5f9;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            padding: 20px;
        }}
        .card {{
            background: #14181f;
            border: 1px solid #23304c;
            border-radius: 20px;
            padding: 36px 30px;
            max-width: 480px;
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
        h1 {{ font-size: 1.5rem; font-weight: 700; margin-bottom: 12px; color: #ffffff; }}
        p {{ color: #94a3b8; font-size: 0.95rem; line-height: 1.5; margin-bottom: 24px; }}
        .footer-note {{ font-size: 0.82rem; color: #64748b; margin-top: 18px; }}
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
