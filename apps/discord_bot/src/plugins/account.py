import crescent
import hikari
import logging
from src.model import Model
from src.hooks import check_is_admin, vip_or_admin, admin_only

logger = logging.getLogger(__name__)

plugin = crescent.Plugin[hikari.GatewayBot, Model]()
from src.groups import player_group


@plugin.include
@player_group.child
@crescent.command(name="link", description="Vincula tu cuenta de Discord con tu Steam ID")
class LinkAccount:
    steam_id = crescent.option(str, "Tu Steam ID de 64 bits")
    usuario = crescent.option(hikari.User, "Usuario a vincular (Solo admin)", default=None)

    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer(ephemeral=True)
        
        target_id = str(ctx.user.id)
        
        if self.usuario:
            is_admin = await check_is_admin(ctx)
            if not is_admin:
                await ctx.respond("❌ Solo los administradores pueden vincular a otros usuarios.")
                return
            target_id = str(self.usuario.id)
            
        try:
            await plugin.model.api.link_account(target_id, self.steam_id)
            
            if self.usuario:
                await ctx.respond(f"✅ Has vinculado a {self.usuario.mention} con el Steam ID `{self.steam_id}`")
            else:
                await ctx.respond(f"✅ Tu cuenta ha sido vinculada exitosamente con el Steam ID `{self.steam_id}`")
        except Exception as e:
            await ctx.respond(f"❌ Error al vincular: {e}")

@plugin.include
@player_group.child
@crescent.command(name="unlink", description="Desvincula tu cuenta de Discord de Steam")
class UnlinkAccount:
    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer(ephemeral=True)
        try:
            discord_id = str(ctx.user.id)
            
            # Remove managed roles first to prevent role leak (Bug 6)
            guild_id = ctx.guild_id
            if guild_id:
                try:
                    res = await plugin.model.api.sync_memberships()
                    role_maps = res.get("role_maps", {})
                    managed_special_roles = res.get("managed_special_roles", [])
                    all_managed_roles = set(role_maps.values()).union(set(managed_special_roles))
                    
                    member = await plugin.app.rest.fetch_member(guild_id, int(discord_id))
                    if member:
                        current_roles = set(member.role_ids)
                        for r_id in all_managed_roles:
                            if r_id in current_roles:
                                await plugin.app.rest.remove_role_from_member(guild_id, int(discord_id), r_id)
                except Exception as e:
                    logger.warning(f"Failed to remove roles during unlink for {discord_id}: {e}")
                    
            await plugin.model.api.unlink_account(discord_id)
            await ctx.respond("✅ Tu cuenta de Discord ha sido desvinculada y tus roles revocados.")
        except Exception as e:
            await ctx.respond(f"❌ Error: {e}")

@plugin.include
@crescent.hook(admin_only)
@plugin.include
@crescent.hook(admin_only)
@player_group.child
@crescent.command(name="welcome_message_set", description="Establece un mensaje de bienvenida personalizado (VIP/ADMIN)")
class SetWelcomeMessage:
    message = crescent.option(str, "El mensaje que se mostrará cuando entres al servidor")
    steam_id: str | None = crescent.option(str, "Steam ID del jugador a editar (opcional)", default=None)
    usuario: hikari.User | None = crescent.option(hikari.User, "Usuario de Discord a editar (opcional)", default=None)

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
            
        steam_data = await plugin.model.api.get_player_by_steam(target_steam)
        active_role = steam_data.get("active_role") if steam_data else None
        
        if not active_role:
            await ctx.respond(f"❌ El jugador no tiene una membresía VIP o ADMIN activa. No se puede establecer el mensaje.")
            return
            
        await plugin.model.api.set_welcome_message(target_steam, self.message)


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
        memberships = steam_data.get("memberships", [])
        special_roles = steam_data.get("special_roles", [])
        active_role = steam_data.get("active_role", "Ninguno")
        if not active_role:
            active_role = "Ninguno"
        
        # We need to fetch the Steam API for the real name if it's not in our DB
        # The API doesn't return it directly in get_player_by_steam yet unless we added it, but let's use what we have.
        in_game_name = steam_data.get("name", steam_data.get("in_game_name", "Desconocido"))
        
        linked_discord = steam_data.get("discord_id", None)
        
        # Build embed
        embed = hikari.Embed(
            title=f"Perfil de Jugador: {in_game_name}",
            description=f"**Steam ID:** {target_steam_id}",
            color=0x2b2d31
        )
            
        if linked_discord:
            embed.add_field(name="🔗 Discord Vinculado", value=f"<@{linked_discord}>", inline=False)
        else:
            embed.add_field(name="🔗 Discord Vinculado", value="No vinculado", inline=False)
            
        # Add roles
        mem_str = "\n".join([f"• {m['type']} (Vence: {m.get('end_time', 'Nunca')})" for m in memberships])
        if not mem_str: mem_str = "Ninguna"
        embed.add_field(name="👑 Membresías Activas", value=mem_str, inline=True)
        
        roles_str = "\n".join([f"• {r}" for r in special_roles])
        if not roles_str: roles_str = "Ninguno"
        embed.add_field(name="🏷️ Roles Especiales", value=roles_str, inline=True)
        
        
        embed.add_field(name="⭐ Rango RCON", value=active_role, inline=False)
        
        # Check permissions for observations
        is_admin = await check_is_admin(ctx)
        is_owner = (target_discord_id == str(ctx.user.id)) if target_discord_id else False
        
        if is_admin or is_owner:
            obs = steam_data.get("observations")
            if obs:
                embed.add_field(name="📝 Observaciones Internas", value=f"`\n{obs}\n`", inline=False)

        
        # Stats
        if stats_data:
            kills = stats_data.get("total_kills", 0)
            deaths = stats_data.get("total_deaths", 0)
            cash = stats_data.get("total_cash", 0)
            matches = stats_data.get("matches_played", 0)
            embed.add_field(name="📊 Estadísticas Históricas", value=f"**Partidas jugadas:** {matches}\n**Kills:** {kills} | **Deaths:** {deaths}\n**Cash total:** ", inline=False)
            
        await ctx.respond(embed=embed)


