import re

with open('d:/proyectos_dev/server_rcon_automation/apps/discord_bot/src/plugins/account.py', 'r', encoding='utf-8') as f:
    content = f.read()

new_class = '''@crescent.command(name="profile", description="Muestra el perfil histórico de un jugador o el tuyo")
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
            
        steam_data = await plugin.model.api.get_player_by_steam(target_steam_id)
        
        if not steam_data:
            await ctx.respond(f"❌ La cuenta de Steam {target_steam_id} no tiene perfil en nuestra base de datos aún (debe entrar a jugar una vez).")
            return
            
        stats_data = await plugin.model.api.get_player_historical_stats(target_steam_id)
            
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
        mem_str = "\\n".join([f"• {m['type']} (Vence: {m.get('end_time', 'Nunca')})" for m in memberships if m.get('is_active')])
        if not mem_str: mem_str = "Ninguna"
        embed.add_field(name="👑 Membresías Activas", value=mem_str, inline=True)
        
        roles_str = "\\n".join([f"• {r}" for r in special_roles])
        if not roles_str: roles_str = "Ninguno"
        embed.add_field(name="🏷️ Roles Especiales", value=roles_str, inline=True)
        
        embed.add_field(name="⭐ Rango RCON", value=active_role, inline=False)
        
        # Stats
        if stats_data:
            kills = stats_data.get("total_kills", 0)
            deaths = stats_data.get("total_deaths", 0)
            cash = stats_data.get("total_cash", 0)
            matches = stats_data.get("matches_played", 0)
            embed.add_field(name="📊 Estadísticas Históricas", value=f"**Partidas jugadas:** {matches}\\n**Kills:** {kills} | **Deaths:** {deaths}\\n**Cash total:** ", inline=False)
            
        await ctx.respond(embed=embed)
'''

pattern = r'@crescent\.command\(name="profile".*?\nclass Profile:(?:\s+.*?\n)+?(?=\s*@plugin\.include|\s*@crescent\.command|$)'
new_content = re.sub(pattern, new_class + '\\n\\n', content)

with open('d:/proyectos_dev/server_rcon_automation/apps/discord_bot/src/plugins/account.py', 'w', encoding='utf-8') as f:
    f.write(new_content)
