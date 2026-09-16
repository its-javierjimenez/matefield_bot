with open("apps/discord_bot/src/plugins/tasks.py", "r", encoding="utf-8") as f:
    content = f.read()

new_task = """
# Tarea para alinear roles de baneados (de DB a Discord)
@plugin.include
@tasks.loop(minutes=5)
async def sync_ban_roles():
    if not plugin.model.api:
        return
        
    try:
        # Sincronizar de RCON a DB
        await plugin.model.api._request("POST", "/api/v1/db/sync_bans")
        
        # Obtener todos los baneos activos
        bans_resp = await plugin.model.api._request("GET", "/api/v1/db/bans")
        bans = bans_resp.get("bans", [])
        active_steam_ids = {b["steam_id"]: b for b in bans if b.get("is_active")}
        
        if not active_steam_ids:
            return
            
        # Obtener mapeos de roles
        configs = await plugin.model.api.get_bot_configs()
        
        # Para RCON puro (permanente), el rol es BAN_ROLE_0
        perm_role_id_str = configs.get("BAN_ROLE_0")
        if not perm_role_id_str:
            return
            
        perm_role_id = int(perm_role_id_str)
            
        # Obtener jugadores vinculados
        res = await plugin.model.api.get_paginated_players(page=1, limit=1000, linked="all")
        players = res.get("players", [])
        
        if not plugin.app.cache.get_guilds_view():
            return
        guild_id = list(plugin.app.cache.get_guilds_view().keys())[0]
        
        for p in players:
            steam_id = p["steam_id"]
            discord_id = int(p["discord_id"])
            
            if steam_id in active_steam_ids:
                ban_entry = active_steam_ids[steam_id]
                # Determinar duración para asignar el rol correcto
                # Si tiene expires_at, calculamos días, pero como simplificación:
                # Si fue importado de RCON, no tiene expires_at, así que es Permanente (0).
                
                # Asignar BAN_ROLE_0 por ahora para sincronizaciones de RCON
                target_role = perm_role_id
                
                # Tratar de ver si ya lo tiene
                try:
                    member = plugin.app.cache.get_member(guild_id, discord_id) or await plugin.app.rest.fetch_member(guild_id, discord_id)
                    if target_role not in member.role_ids:
                        await member.add_role(target_role, reason="Ban sincronizado desde RCON/DB")
                        logger.info(f"[Bans] Rol permanente asignado a {discord_id} por sync.")
                except Exception as e:
                    pass
    except Exception as e:
        logger.error(f"[Bans Task] Error sincronizando roles de ban: {e}")
"""

if "sync_ban_roles" not in content:
    content += new_task
    with open("apps/discord_bot/src/plugins/tasks.py", "w", encoding="utf-8") as f:
        f.write(content)
    print("Added sync_ban_roles task")
