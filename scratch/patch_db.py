import re

with open("apps/discord_bot/src/plugins/database.py", "r", encoding="utf-8") as f:
    content = f.read()

old_block = """        try:
            res = await plugin.model.api.get_reserved_slots()
            slots = res.reservedSlots if res else []
            if not slots:
                await ctx.respond("?? No hay slots reservados actualmente en el RCON.")
                return
                
            mentions = "\\n".join([f"- `{s}`" for s in slots])
            embed = hikari.Embed(
                title=f"?? Slots Reservados en RCON ({len(slots)})",
                description=mentions,
                color=0x4169E1
            )
            await ctx.respond(embed=embed)
        except Exception as e:
            await ctx.respond(f"? Error obteniendo slots reservados: {e}")"""

new_block = """        try:
            res = await plugin.model.api.get_reserved_slots()
            slots = res.reservedSlots if res else []
            if not slots:
                await ctx.respond("?? No hay slots reservados actualmente en el RCON.")
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
                
            # Cut into chunks if necessary
            desc = "\\n".join(lines)
            if len(desc) <= 4096:
                embed = hikari.Embed(
                    title=f"?? Slots Reservados en RCON ({len(slots)})",
                    description=desc,
                    color=0x4169E1
                )
                await ctx.respond(embed=embed)
            else:
                await ctx.respond(f"Hay demasiados jugadores ({len(slots)}) para mostrar en un embed. Usa `/reserved_slots list` en vez.")
        except Exception as e:
            await ctx.respond(f"? Error obteniendo slots reservados: {e}")"""


start_idx = content.find("        try:\n            res = await plugin.model.api.get_reserved_slots()")
end_str = "Error obteniendo slots reservados: {e}\")"
end_idx = content.find(end_str, start_idx) + len(end_str)

if start_idx != -1 and end_idx != -1:
    new_content = content[:start_idx] + new_block.replace("\\n", "\n") + content[end_idx:]
    with open("apps/discord_bot/src/plugins/database.py", "w", encoding="utf-8") as f:
        f.write(new_content)
    print("Success: database.py modified")
else:
    print("Could not find start or end index for block replacement")
