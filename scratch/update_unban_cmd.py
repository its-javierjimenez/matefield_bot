with open("apps/discord_bot/src/plugins/admin.py", "r", encoding="utf-8") as f:
    content = f.read()

import re

old_unban = """class UnbanPlayer:
    steam_id = crescent.option(str, "Steam ID a desbanear")
    
    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer()
        try:
            await plugin.model.api.unban_player(str(self.steam_id))
            await ctx.respond(f"? Jugador `{self.steam_id}` ha sido desbaneado y sincronizado con RCON.")
        except Exception as e:
            await ctx.respond(f"? Error al desbanear: {e}")"""

new_unban = """class UnbanPlayer:
    steam_id = crescent.option(str, "Steam ID a desbanear")
    
    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer()
        try:
            await plugin.model.api.unban_player(str(self.steam_id))
            msg = f"? Jugador `{self.steam_id}` ha sido desbaneado y sincronizado con RCON."
            
            # Quitar posibles roles de ban
            db_player = await plugin.model.api.get_player_by_steam(str(self.steam_id))
            if db_player and db_player.get("discord_id"):
                discord_id = int(db_player["discord_id"])
                
                configs = await plugin.model.api.get_bot_configs()
                ban_roles = [int(v) for k, v in configs.items() if k.startswith("BAN_ROLE_") and v.isdigit()]
                
                if ban_roles:
                    try:
                        member = ctx.app.cache.get_member(ctx.guild_id, discord_id) or await ctx.app.rest.fetch_member(ctx.guild_id, discord_id)
                        removed = 0
                        for role_id in ban_roles:
                            if role_id in member.role_ids:
                                await member.remove_role(role_id, reason="Desbaneado")
                                removed += 1
                        if removed > 0:
                            msg += f"\n? Se quitaron {removed} roles de ban al usuario <@{discord_id}>."
                    except Exception as ex:
                        msg += f"\n?? No se pudieron quitar los roles de Discord: {ex}"
                        
            await ctx.respond(msg)
        except Exception as e:
            await ctx.respond(f"? Error al desbanear: {e}")"""

content = content.replace(old_unban, new_unban)

with open("apps/discord_bot/src/plugins/admin.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Updated admin.py unban command")
