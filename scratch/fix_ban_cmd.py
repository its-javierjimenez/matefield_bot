import re

with open("d:/proyectos_dev/matefield_bot/apps/discord_bot/src/plugins/admin.py", "r", encoding="utf-8") as f:
    content = f.read()

old_ban = '''class BanPlayer:
    steam_id = crescent.option(str, "Steam ID a banear")
    reason = crescent.option(str, "Razón del ban", default="No especificado")
    
    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer()
        try:
            await plugin.model.api.ban_player(str(self.steam_id), str(self.reason))
            await ctx.respond(f"✅ Jugador `{self.steam_id}` ha sido baneado permanentemente en la base de datos y RCON. Razón: {self.reason}")
        except Exception as e:
            await ctx.respond(f"❌ Error al banear: {e}")'''

new_ban = '''class BanPlayer:
    steam_id = crescent.option(str, "Steam ID a banear")
    reason = crescent.option(str, "Razón del ban", default="No especificado")
    dias = crescent.option(int, "Duración en días (0 = permanente)", default=0)
    
    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer()
        try:
            # 1. Ban en DB y RCON
            await plugin.model.api.ban_player(str(self.steam_id), str(self.reason), self.dias)
            
            dur_str = "permanentemente" if self.dias == 0 else f"por {self.dias} días"
            msg = f"✅ Jugador `{self.steam_id}` baneado {dur_str}. Razón: {self.reason}"
            
            # 2. Asignar rol en Discord si está vinculado y mapeado
            try:
                db_player = await plugin.model.api.get_player_by_steam(str(self.steam_id))
                if db_player and db_player.get("discord_id"):
                    discord_id = int(db_player["discord_id"])
                    ban_role_id = await plugin.model.api.get_bot_config(f"BAN_ROLE_{self.dias}")
                    if ban_role_id:
                        member = ctx.app.cache.get_member(ctx.guild_id, discord_id) or await ctx.app.rest.fetch_member(ctx.guild_id, discord_id)
                        await member.add_role(int(ban_role_id), reason=f"Baneado {dur_str}")
                        msg += f"\\n🔒 Rol <@&{ban_role_id}> asignado a <@{discord_id}>."
            except Exception as ex:
                msg += f"\\n⚠️ No se pudo asignar el rol en Discord: {ex}"
            
            await ctx.respond(msg)
        except Exception as e:
            await ctx.respond(f"❌ Error al banear: {e}")'''

if old_ban in content:
    content = content.replace(old_ban, new_ban)
    with open("d:/proyectos_dev/matefield_bot/apps/discord_bot/src/plugins/admin.py", "w", encoding="utf-8") as f:
        f.write(content)
    print("Fixed admin.py BanPlayer")
else:
    print("Pattern not found, trying alternative...")
    # Find the class by regex
    idx = content.find("class BanPlayer:")
    if idx >= 0:
        # Find the next class or decorator
        end_markers = ["@plugin.include", "class Unban"]
        end_idx = len(content)
        for m in end_markers:
            pos = content.find(m, idx + 10)
            if pos >= 0 and pos < end_idx:
                end_idx = pos
        
        old_block = content[idx:end_idx]
        print(f"Found block ({len(old_block)} chars):")
        print(repr(old_block[:200]))
