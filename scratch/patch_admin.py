import re

with open("apps/discord_bot/src/plugins/admin.py", "r", encoding="utf-8") as f:
    content = f.read()

old_block = """        try:
            data = await plugin.model.api.get_reserved_slots()
            slots = data.reservedSlots or []
            
            if not slots:
                await ctx.respond("No hay slots reservados configurados.")
                return
                
            msg = "**Steam IDs Reservados:**\\n"
            msg += "\\n".join([f"- `{s}`" for s in slots])
            await ctx.respond(msg)
        except Exception as e:
            await ctx.respond(f"? Error al consultar RCON: {e}")"""

new_block = """        try:
            data = await plugin.model.api.get_reserved_slots()
            slots = data.reservedSlots or []
            
            if not slots:
                await ctx.respond("No hay slots reservados configurados.")
                return
                
            steam_profiles = await plugin.model.api.get_steam_players_batch(slots)
            
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
                lines.append(f"- `{s}` | Steam: **{steam_name}** | Discord: **{discord_username}**")
                
            msg = "**Jugadores en Slots Reservados:**\\n"
            current_msg = msg
            for line in lines:
                if len(current_msg) + len(line) + 1 > 1900:
                    await ctx.respond(current_msg)
                    current_msg = ""
                current_msg += line + "\\n"
            
            if current_msg:
                await ctx.respond(current_msg)
        except Exception as e:
            await ctx.respond(f"Error al consultar RCON o DB: {e}")"""

# Reemplazamos quitando el emoji '?' que causaba problemas de decodificación
old_block_safe = re.sub(r'\? Error al consultar', r' Error al consultar', old_block)

# Try exact string replace first
if "data = await plugin.model.api.get_reserved_slots()" in content:
    # find the block manually
    start_idx = content.find("        try:\n            data = await plugin.model.api.get_reserved_slots()")
    end_str = "Error al consultar RCON: {e}\")"
    end_idx = content.find(end_str, start_idx) + len(end_str)
    
    if start_idx != -1 and end_idx != -1:
        new_content = content[:start_idx] + new_block.replace("\\n", "\n") + content[end_idx:]
        with open("apps/discord_bot/src/plugins/admin.py", "w", encoding="utf-8") as f:
            f.write(new_content)
        print("Success: admin.py modified")
    else:
        print("Could not find start or end index for block replacement")
else:
    print("Could not find target string in content")
