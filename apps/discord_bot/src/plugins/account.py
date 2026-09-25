import crescent
import hikari
import logging
from src.model import Model
from src.hooks import check_is_admin, vip_or_admin, admin_only

logger = logging.getLogger(__name__)

plugin = crescent.Plugin[hikari.GatewayBot, Model]()
from src.groups import player_group
from wardogs_schemas.steam_token import create_steam_link_token


@plugin.include
@player_group.child
@crescent.command(name="link", description="Vincula tu cuenta de Discord con Steam de forma segura")
class LinkAccount:
    steam_id = crescent.option(str, "Steam ID (Solo administración / soporte)", default=None)
    usuario = crescent.option(hikari.User, "Usuario a vincular (Solo administración)", default=None)

    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer(ephemeral=True)

        # 1. Flujo automático sin parámetros: Genera enlace seguro de Steam OpenID
        if not self.steam_id and not self.usuario:
            secret_key = plugin.model.api.api_key
            token = create_steam_link_token(
                discord_id=str(ctx.user.id),
                secret_key=secret_key,
                guild_id=str(ctx.guild_id) if ctx.guild_id else None
            )
            public_url = plugin.model.public_api_url.rstrip("/")
            link_url = f"{public_url}/api/v1/auth/steam/login?token={token}"

            embed = hikari.Embed(
                title="🎮 Vinculación con Steam",
                description=(
                    f"Hola {ctx.user.mention},\n\n"
                    "Para vincular tu cuenta de Steam de forma segura y automática, "
                    "haz clic en el botón de abajo para iniciar sesión directamente en Steam.\n\n"
                    "🔒 **Seguro:** La autenticación se realiza de forma directa en los servidores de Valve (Steam).\n"
                    "⏱️ **Vigencia:** Este enlace personal expira en 10 minutos."
                ),
                color=0x1b2838
            )
            row = ctx.app.rest.build_message_action_row()
            row.add_link_button(link_url, label="Iniciar sesión con Steam", emoji="🎮")
            await ctx.respond(embed=embed, components=[row], ephemeral=True)
            return

        # 2. Flujo manual con parámetros: Exclusivo para administradores
        is_admin = await check_is_admin(ctx)
        if not is_admin:
            await ctx.respond(
                "❌ La vinculación manual con Steam ID está reservada para administradores.\n"
                "Para vincular tu propia cuenta de Steam de forma segura, ejecuta `/player link` sin parámetros.",
                ephemeral=True
            )
            return

        if not self.steam_id:
            await ctx.respond("❌ Debes especificar un Steam ID válido para vincular manualmente.", ephemeral=True)
            return

        target_id = str(self.usuario.id) if self.usuario else str(ctx.user.id)
            
        try:
            await plugin.model.api.link_account(target_id, str(self.steam_id))
            
            link_msg = ""
            guild_id = ctx.guild_id
            if guild_id:
                try:
                    try:
                        member = await ctx.app.rest.fetch_member(guild_id, int(target_id))
                    except Exception:
                        member = plugin.app.cache.get_member(guild_id, int(target_id))
                    if member:
                        # Verificar si el Steam ID posee un baneo activo en DB (incluyendo solo_discord)
                        bans_resp = await plugin.model.api.get_db_bans(str(self.steam_id))
                        active_bans = [b for b in (bans_resp.bans if bans_resp else []) if b.is_active]
                        
                        if active_bans:
                            ban_role_id = await plugin.model.api.get_bot_config("BAN_ROLE_DEFAULT")
                            if ban_role_id and ban_role_id.isdigit() and int(ban_role_id) not in member.role_ids:
                                await member.add_role(int(ban_role_id), reason="Baneo activo detectado al vincular cuenta")
                                link_msg += f"\n🔒 Rol de sanción <@&{ban_role_id}> asignado automáticamente."
                                
                            unset_role_id = await plugin.model.api.get_bot_config("BAN_UNSET_ROLE_ID")
                            if unset_role_id and unset_role_id.isdigit() and int(unset_role_id) in member.role_ids:
                                await member.remove_role(int(unset_role_id), reason="Baneo activo: rol revocado al vincular")
                                link_msg += f"\n🔓 Rol <@&{unset_role_id}> removido."
                        else:
                            link_role_id = await plugin.model.api.get_bot_config("LINK_ROLE_ID")
                            if link_role_id and link_role_id.isdigit() and int(link_role_id) not in member.role_ids:
                                await member.add_role(int(link_role_id), reason="Rol asignado por vincular cuenta (/player link)")
                                link_msg = f"\n🔗 Rol <@&{link_role_id}> asignado automáticamente."
                except Exception as ex:
                    logger.warning(f"No se pudieron actualizar los roles al vincular {target_id}: {ex}")
            
            if self.usuario:
                await ctx.respond(f"✅ Has vinculado a {self.usuario.mention} con el Steam ID `{self.steam_id}`{link_msg}")
            else:
                await ctx.respond(f"✅ Tu cuenta ha sido vinculada exitosamente con el Steam ID `{self.steam_id}`{link_msg}")
        except Exception as e:
            await ctx.respond(f"❌ Error al vincular: {e}")


@plugin.include
@player_group.child
@crescent.command(name="link_channel", description="Publica un panel permanente con botón para vincular cuentas de Steam")
class LinkChannel:
    canal = crescent.option(hikari.InteractionChannel, "Canal donde publicar el mensaje (Por defecto el canal actual)", default=None)

    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer(ephemeral=True)
        is_admin = await check_is_admin(ctx)
        if not is_admin:
            await ctx.respond("❌ Solo los administradores pueden publicar el panel de vinculación.", ephemeral=True)
            return

        target_channel_id = self.canal.id if self.canal else ctx.channel_id
        
        embed = hikari.Embed(
            title="🔗 Vinculación Oficial de Cuentas | Matefield",
            description=(
                "¡Bienvenido a los servidores de **Matefield**!\n\n"
                "Para obtener tu rol de miembro verificado, sincronizar membresías VIP, "
                "guardar tus estadísticas de juego y acceder a los servidores protegidos, "
                "debes vincular tu cuenta oficial de Steam con Discord.\n\n"
                "👉 **Haz clic en el botón de abajo para iniciar la vinculación.**"
            ),
            color=0x2b6cb0
        )
        embed.set_footer(text="Autenticación oficial y segura provista por Steam OpenID")
        
        row = ctx.app.rest.build_message_action_row()
        row.add_interactive_button(
            hikari.ButtonStyle.PRIMARY,
            "btn_start_steam_link",
            label="Vincular mi cuenta de Steam",
            emoji="🎮"
        )
        
        try:
            # Borrar panel anterior si existe para garantizar idempotencia
            old_chan = await plugin.model.api.get_bot_config("LINK_PANEL_CHANNEL_ID")
            old_msg = await plugin.model.api.get_bot_config("LINK_PANEL_MESSAGE_ID")
            if old_chan and old_msg and old_chan.isdigit() and old_msg.isdigit():
                try:
                    await ctx.app.rest.delete_message(int(old_chan), int(old_msg))
                except Exception:
                    pass

            new_msg = await ctx.app.rest.create_message(target_channel_id, embed=embed, components=[row])
            await plugin.model.api.set_bot_config("LINK_PANEL_CHANNEL_ID", str(target_channel_id))
            await plugin.model.api.set_bot_config("LINK_PANEL_MESSAGE_ID", str(new_msg.id))

            await ctx.respond(f"✅ Panel de vinculación publicado exitosamente en <#{target_channel_id}>.", ephemeral=True)
        except Exception as e:
            await ctx.respond(f"❌ Error al publicar en el canal: {e}", ephemeral=True)


@plugin.include
@crescent.event
async def on_steam_link_button_click(event: hikari.InteractionCreateEvent) -> None:
    if not isinstance(event.interaction, hikari.ComponentInteraction):
        return
    if event.interaction.custom_id == "btn_start_steam_link":
        try:
            secret_key = plugin.model.api.api_key
            token = create_steam_link_token(
                discord_id=str(event.interaction.user.id),
                secret_key=secret_key,
                guild_id=str(event.interaction.guild_id) if event.interaction.guild_id else None
            )
            public_url = plugin.model.public_api_url.rstrip("/")
            link_url = f"{public_url}/api/v1/auth/steam/login?token={token}"
            
            embed = hikari.Embed(
                title="🎮 Vinculación con Steam",
                description=(
                    f"Hola <@{event.interaction.user.id}>,\n\n"
                    "Haz clic en el siguiente botón para iniciar sesión en Steam y verificar tu cuenta de forma 100% segura.\n\n"
                    "🔒 **Seguro:** La autenticación se realiza de forma directa en los servidores de Valve (Steam).\n"
                    "⏱️ **Vigencia:** Este enlace personal expira en 10 minutos."
                ),
                color=0x1b2838
            )
            row = plugin.app.rest.build_message_action_row()
            row.add_link_button(link_url, label="Iniciar sesión con Steam", emoji="🎮")
            
            await event.interaction.create_initial_response(
                hikari.ResponseType.MESSAGE_CREATE,
                embed=embed,
                components=[row],
                flags=hikari.MessageFlag.EPHEMERAL
            )
        except Exception as e:
            logger.error(f"[Steam Link Button] Error al procesar interacción: {e}", exc_info=True)



@plugin.include
@player_group.child
@crescent.command(name="unlink", description="Desvincula tu cuenta de Discord de Steam")
class UnlinkAccount:
    usuario = crescent.option(hikari.User, "Usuario a desvincular (Solo admin)", default=None)

    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer(ephemeral=True)
        
        discord_id = str(ctx.user.id)
        if self.usuario:
            is_admin = await check_is_admin(ctx)
            if not is_admin:
                await ctx.respond("❌ Solo los administradores pueden desvincular a otros usuarios.")
                return
            discord_id = str(self.usuario.id)

        try:
            # Remove managed roles first to prevent role leak (Bug 6)
            guild_id = ctx.guild_id
            if guild_id:
                try:
                    res = await plugin.model.api.sync_memberships()
                    role_maps = res.get("role_maps", {})
                    managed_special_roles = res.get("managed_special_roles", [])
                    all_managed_roles = set(role_maps.values()).union(set(managed_special_roles))
                    
                    link_role_id = await plugin.model.api.get_bot_config("LINK_ROLE_ID")
                    if link_role_id and link_role_id.isdigit():
                        all_managed_roles.add(int(link_role_id))
                    
                    bot_app = getattr(ctx, "app", None) or plugin.app
                    member = await bot_app.rest.fetch_member(guild_id, int(discord_id))
                    if member:
                        current_roles = set(member.role_ids)
                        for r_id in all_managed_roles:
                            if r_id in current_roles:
                                await bot_app.rest.remove_role_from_member(guild_id, int(discord_id), r_id)
                except Exception as e:
                    logger.warning(f"Failed to remove roles during unlink for {discord_id}: {e}")
                    
            await plugin.model.api.unlink_account(discord_id)
            if self.usuario:
                await ctx.respond(f"✅ La cuenta de {self.usuario.mention} ha sido desvinculada y sus roles revocados.")
            else:
                await ctx.respond("✅ Tu cuenta de Discord ha sido desvinculada y tus roles revocados.")
        except Exception as e:
            await ctx.respond(f"❌ Error: {e}")

@plugin.include
@crescent.hook(admin_only)
@player_group.child
@crescent.command(name="welcome_message_set", description="Establece un mensaje de bienvenida personalizado (VIP/ADMIN)")
class SetWelcomeMessage:
    message = crescent.option(str, "El mensaje que se mostrará cuando entres al servidor")
    steam_id = crescent.option(str, "Steam ID del jugador a editar (opcional)", default=None)
    usuario = crescent.option(hikari.User, "Usuario de Discord a editar (opcional)", default=None)

    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer(ephemeral=False)
        
        if len(self.message) > 60:
            await ctx.respond("❌ El mensaje no puede tener más de 60 caracteres.")
            return
            
        target_steam = self.steam_id
        if self.usuario:
            db_player = await plugin.model.api.get_player_by_discord(str(self.usuario.id))
            if not db_player:
                await ctx.respond(f"❌ El usuario {self.usuario.mention} no tiene una cuenta vinculada.")
                return
            target_steam = db_player.get("steam_id")
            
        if not target_steam:
            discord_id = str(ctx.user.id)
            user_data = await plugin.model.api.get_player_by_discord(discord_id)
            if not user_data or not user_data.get("steam_id"):
                await ctx.respond("❌ Debes vincular tu cuenta de Steam primero usando `/player link` o especificar a quién editar.")
                return
            target_steam = user_data["steam_id"]
            
        steam_data = await plugin.model.api.get_player_by_steam(str(target_steam))
        active_role = steam_data.get("active_role") if steam_data else None
        
        if not active_role:
            await ctx.respond(f"❌ El jugador no tiene una membresía VIP o ADMIN activa. No se puede establecer el mensaje.")
            return
            
        await plugin.model.api.set_welcome_message(str(target_steam), self.message)
        preview_msg = f"El {active_role} [Nombre en Juego] se conectó: \"{self.message}\""
        await ctx.respond(f"✅ **Mensaje de bienvenida establecido.**\n👀 **Vista Previa:**\n> {preview_msg}")

@plugin.include
@player_group.child
@crescent.command(name="profile", description="Muestra el perfil histórico de un jugador o el tuyo")
class Profile:
    usuario = crescent.option(hikari.User, "Usuario de Discord a consultar (opcional)", default=None)
    steam_id = crescent.option(str, "Steam ID a consultar (opcional)", default=None)

    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer(ephemeral=False)
        
        target_discord_id = str(self.usuario.id) if self.usuario else None
        target_steam_id = self.steam_id
        
        # If no arguments provided, use caller
        if not target_discord_id and not target_steam_id:
            target_discord_id = str(ctx.user.id)
            
        user_data = None
        if target_discord_id:
            user_data = await plugin.model.api.get_player_by_discord(target_discord_id)
            if not user_data or not user_data.get("steam_id"):
                if target_discord_id == str(ctx.user.id):
                    await ctx.respond("❌ No tienes ninguna cuenta de Steam vinculada. Usa /player link primero.")
                else:
                    await ctx.respond("❌ Ese usuario no tiene cuenta de Steam vinculada.")
                return
            target_steam_id = user_data["steam_id"]
            
        steam_data = await plugin.model.api.get_player_by_steam(str(target_steam_id))
        
        if not steam_data:
            await ctx.respond(f"❌ La cuenta de Steam {target_steam_id} no tiene perfil en nuestra base de datos aún (debe entrar a jugar una vez).")
            return
            
        stats_data = await plugin.model.api.get_player_historical_stats(str(target_steam_id))
            
        # Parse data
        memberships = steam_data.get("active_memberships") or steam_data.get("memberships", [])
        special_roles = steam_data.get("special_roles", [])
        active_role = steam_data.get("active_role", "Ninguno")
        if not active_role:
            active_role = "Ninguno"
        
        # We need to fetch the Steam API for the real name if it's not in our DB
        in_game_name = steam_data.get("name") or steam_data.get("in_game_name") or "Desconocido"
        
        linked_discord = steam_data.get("discord_id", None)
        
        # Build embed
        embed = hikari.Embed(
            title=f"Perfil de Jugador: {in_game_name}",
            description=f"**Steam ID:** {target_steam_id}",
            color=0x2b2d31
        )
        avatar_url = steam_data.get("avatar_url")
        if avatar_url:
            embed.set_thumbnail(avatar_url)
            
        if linked_discord:
            embed.add_field(name="🔗 Discord Vinculado", value=f"<@{linked_discord}>", inline=False)
        else:
            embed.add_field(name="🔗 Discord Vinculado", value="No vinculado", inline=False)
            
        # Add roles
        mem_str = "\n".join([f"• {m['type']} (Vence: {m.get('end_time') or 'Permanente'})" for m in memberships])
        if not mem_str: mem_str = "Ninguna"
        embed.add_field(name="👑 Membresías Activas", value=mem_str, inline=True)
        
        roles_str = "\n".join([f"• {r}" for r in special_roles])
        if not roles_str: roles_str = "Ninguno"
        embed.add_field(name="🏷️ Roles Especiales", value=roles_str, inline=True)
        
        
        # Rango RCON y Observaciones Internas solo son visibles si un administrador usa el comando
        is_admin = await check_is_admin(ctx)
        if is_admin:
            embed.add_field(name="⭐ Rango RCON", value=active_role, inline=False)
            obs = steam_data.get("observations")
            if obs:
                embed.add_field(name="📝 Observaciones Internas", value=f"```{obs}```", inline=False)

        
        # Stats
        if stats_data:
            kills = stats_data.get("total_kills", 0)
            deaths = stats_data.get("total_deaths", 0)
            cash = stats_data.get("total_cash_earned", stats_data.get("total_cash", 0))
            matches = stats_data.get("matches_played", 0)
            embed.add_field(name="📊 Estadísticas Históricas", value=f"**Partidas jugadas:** {matches}\n**Kills:** {kills} | **Deaths:** {deaths}\n**Cash total:** ${cash}", inline=False)
            
        await ctx.respond(embed=embed)


