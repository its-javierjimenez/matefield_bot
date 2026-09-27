import html
import logging
from pathlib import Path
from typing import Optional, Dict

logger = logging.getLogger("wardogs.auth_pages")

PAGES_DIR = Path(__file__).resolve().parents[4] / "pages" / "steam"
SUCCESS_TEMPLATE_PATH = PAGES_DIR / "success_callback.html"
ERROR_TEMPLATE_PATH = PAGES_DIR / "error_callback.html"


class AuthPageService:
    """
    Servicio desacoplado para la resolución de perfiles y renderizado
    de las interfaces de callback de autenticación Steam OpenID.
    Utiliza exclusivamente plantillas HTML externas ubicadas en pages/steam/.
    """

    @classmethod
    def _load_template(cls, template_path: Path) -> str:
        """Carga el contenido de la plantilla HTML desde el disco de forma segura."""
        if not template_path.is_file():
            logger.error("Plantilla HTML no encontrada en el sistema: %s", template_path)
            raise FileNotFoundError(f"Plantilla HTML '{template_path.name}' no encontrada en el servidor.")
        return template_path.read_text(encoding="utf-8")

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
            import httpx
            async with httpx.AsyncClient(timeout=4.0) as dc:
                res = await dc.get(
                    f"https://discord.com/api/v10/users/{discord_id}",
                    headers={"Authorization": f"Bot {discord_token}"},
                )
                if res.status_code == 200:
                    udata = res.json()
                    result["username"] = udata.get("global_name") or udata.get("username")
                    disc = udata.get("discriminator", "0")
                    username = udata.get("username", "")
                    result["tag"] = f"#{disc}" if disc != "0" else (f"@{username}" if username else "")
                    av_hash = udata.get("avatar")
                    if av_hash:
                        ext = "gif" if av_hash.startswith("a_") else "png"
                        result["avatar_url"] = f"https://cdn.discordapp.com/avatars/{discord_id}/{av_hash}.{ext}"
        except Exception as ex:
            logger.debug("No se pudo resolver el perfil de Discord para %s: %s", discord_id, ex)

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

        content = cls._load_template(SUCCESS_TEMPLATE_PATH)
        replacements = {
            "{{DISCORD_NAME}}": html.escape(discord_name_val),
            "{{DISCORD_TAG}}": html.escape(discord_tag_val),
            "{{DISCORD_ID}}": html.escape(discord_id_val),
            "{{DISCORD_AVATAR}}": html.escape(discord_avatar_val, quote=True),
            "{{STEAM_NAME}}": html.escape(steam_name_val),
            "{{STEAM_ID}}": html.escape(steam_id_val),
            "{{STEAM_AVATAR}}": html.escape(steam_avatar_val, quote=True),
            "{{STEAM_PROFILE_URL}}": html.escape(steam_profile_val, quote=True),
        }
        for placeholder, val in replacements.items():
            content = content.replace(placeholder, val)
        return content

    @classmethod
    def render_error_page(
        cls,
        title: str,
        message: str,
        detail: Optional[str] = "",
    ) -> str:
        """Renderiza error_callback.html inyectando el motivo de error dinámico."""
        content = cls._load_template(ERROR_TEMPLATE_PATH)
        replacements = {
            "{{ERROR_TITLE}}": html.escape(title or "Error de vinculación"),
            "{{ERROR_MESSAGE}}": html.escape(message or "Ocurrió un error inesperado al procesar la vinculación."),
            "{{ERROR_DETAIL}}": html.escape(detail or ""),
        }
        for placeholder, val in replacements.items():
            content = content.replace(placeholder, val)
        return content
