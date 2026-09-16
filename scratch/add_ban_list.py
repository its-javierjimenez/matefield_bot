with open("apps/discord_bot/src/plugins/admin.py", "r", encoding="utf-8") as f:
    content = f.read()

import re

new_cmd = """
# Grupo Bans
ban_group = crescent.Group("ban", description="Administración de baneos", hooks=[admin_only])

@plugin.include
@ban_group.child
@crescent.command(name="list", description="Muestra la lista de baneos, con opción de filtrar")
class BanList:
    steam_id = crescent.option(str, "Filtrar por Steam ID", default=None)
    usuario = crescent.option(hikari.User, "Filtrar por usuario de Discord", default=None)

    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer()
        try:
            target_steam = self.steam_id
            
            if self.usuario:
                db_player = await plugin.model.api.get_player_by_discord(str(self.usuario.id))
                if not db_player:
                    await ctx.respond(f"El usuario {self.usuario.mention} no tiene una cuenta vinculada.")
                    return
                target_steam = db_player.get("steam_id")
                
            data = await plugin.model.api.get_db_bans(target_steam)
            bans = data.bans if data else []
            
            if not bans:
                msg = "No hay baneos registrados."
                if target_steam:
                    msg = f"El Steam ID `{target_steam}` no tiene baneos activos."
                await ctx.respond(msg)
                return
                
            slots = [b.steam_id for b in bans]
            steam_profiles = await plugin.model.api.get_steam_players_batch(slots)
            
            # 1. Fetch DB players concurrentemente
            db_players_list = await asyncio.gather(*[plugin.model.api.get_player_by_steam(s) for s in slots])
            db_players = dict(zip(slots, db_players_list))
            
            async def resolve_discord_username(db_player_info):
                if not db_player_info or not db_player_info.get("discord_id"):
                    return "Desconocido"
                discord_id = int(db_player_info.get("discord_id"))
                cached_user = ctx.app.cache.get_user(discord_id)
                if cached_user:
                    return cached_user.username
                try:
                    user = await ctx.app.rest.fetch_user(discord_id)
                    return user.username
                except:
                    return f"ID: {discord_id}"
            
            # 2. Fetch Discord usernames concurrentemente
            discord_usernames = await asyncio.gather(*[resolve_discord_username(db_players.get(s)) for s in slots])
            discord_usernames_dict = dict(zip(slots, discord_usernames))
            
            lines = []
            for b in bans:
                steam_name = steam_profiles.get(b.steam_id, {}).get("personaname", "Desconocido")
                discord_username = discord_usernames_dict.get(b.steam_id, "Desconocido")
                lines.append(f"- `{b.steam_id}` | Steam: **{steam_name}** | Discord: **{discord_username}** | Razón: _{b.reason}_")
                
            msg = f"**Jugadores Baneados ({len(bans)}):**\n"
            current_msg = msg
            for line in lines:
                if len(current_msg) + len(line) + 1 > 1900:
                    await ctx.respond(current_msg)
                    current_msg = ""
                current_msg += line + "\n"
            
            if current_msg:
                await ctx.respond(current_msg)
        except Exception as e:
            await ctx.respond(f"Error al consultar la base de datos: {e}")
"""

if "ban_group = crescent.Group" not in content:
    content += new_cmd
    
with open("apps/discord_bot/src/plugins/admin.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Added ban list to admin.py")
