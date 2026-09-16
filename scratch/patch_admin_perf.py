with open("apps/discord_bot/src/plugins/admin.py", "r", encoding="utf-8") as f:
    content = f.read()

import re
import asyncio

old_code = """            steam_profiles = await plugin.model.api.get_steam_players_batch(slots)
            
            lines = []
            for s in slots:
                db_player = await plugin.model.api.get_player_by_steam(s)
                
                discord_username = "Desconocido"
                if db_player and db_player.get("discord_id"):
                    discord_id = db_player.get("discord_id")
                    try:
                        user = await ctx.app.rest.fetch_user(int(discord_id))
                        discord_username = user.username
                    except:
                        discord_username = f"ID: {discord_id}"
                        
                steam_name = steam_profiles.get(s, {}).get("personaname", "Desconocido")
                lines.append(f"- `{s}` | Steam: **{steam_name}** | Discord: **{discord_username}**")"""

new_code = """            steam_profiles = await plugin.model.api.get_steam_players_batch(slots)
            
            # 1. Optimización: Fetch DB players concurrentemente
            db_players_list = await asyncio.gather(*[plugin.model.api.get_player_by_steam(s) for s in slots])
            db_players = dict(zip(slots, db_players_list))
            
            async def resolve_discord_username(db_player_info):
                if not db_player_info or not db_player_info.get("discord_id"):
                    return "Desconocido"
                discord_id = int(db_player_info.get("discord_id"))
                
                # Check cache primero (0 costo)
                cached_user = ctx.app.cache.get_user(discord_id)
                if cached_user:
                    return cached_user.username
                    
                # Si no, buscar en la API
                try:
                    user = await ctx.app.rest.fetch_user(discord_id)
                    return user.username
                except:
                    return f"ID: {discord_id}"
            
            # 2. Optimización: Fetch Discord usernames concurrentemente (reduciendo a 1-2 segundos)
            discord_usernames = await asyncio.gather(*[resolve_discord_username(db_players.get(s)) for s in slots])
            discord_usernames_dict = dict(zip(slots, discord_usernames))
            
            lines = []
            for s in slots:
                steam_name = steam_profiles.get(s, {}).get("personaname", "Desconocido")
                discord_username = discord_usernames_dict.get(s, "Desconocido")
                lines.append(f"- `{s}` | Steam: **{steam_name}** | Discord: **{discord_username}**")"""

content = content.replace(old_code, new_code)

if "import asyncio" not in content:
    content = "import asyncio\n" + content

with open("apps/discord_bot/src/plugins/admin.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Updated admin.py")
