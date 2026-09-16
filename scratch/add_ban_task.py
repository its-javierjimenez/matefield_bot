with open("apps/discord_bot/src/plugins/tasks.py", "r", encoding="utf-8") as f:
    content = f.read()

new_task = """
# Tarea para revisar baneos expirados
@plugin.include
@tasks.loop(minutes=1)
async def check_expired_bans():
    if not plugin.model.api:
        return
        
    try:
        bans = await plugin.model.api._request("GET", "/api/v1/db/bans")
        bans = bans.get("bans", [])
        
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        
        expired_bans = []
        for b in bans:
            if not b.get("is_active"):
                continue
            expires_at_str = b.get("expires_at")
            if not expires_at_str:
                continue
                
            try:
                expires_at = datetime.fromisoformat(expires_at_str)
                if expires_at < now:
                    expired_bans.append(b)
            except ValueError:
                pass
                
        if not expired_bans:
            return
            
        logger.info(f"[Bans] Encontrados {len(expired_bans)} baneos expirados.")
        
        # Obtener configuracion de roles de ban
        configs = await plugin.model.api.get_bot_configs()
        ban_roles = [int(v) for k, v in configs.items() if k.startswith("BAN_ROLE_") and v.isdigit()]
        
        # Desbanear
        for b in expired_bans:
            steam_id = b["steam_id"]
            logger.info(f"[Bans] Desbaneando {steam_id} por expiración...")
            # Unban en la API (esto quita de DB y RCON)
            await plugin.model.api.unban_player(steam_id)
            
            # Quitar roles en Discord
            db_player = await plugin.model.api.get_player_by_steam(steam_id)
            if db_player and db_player.get("discord_id") and ban_roles:
                discord_id = int(db_player["discord_id"])
                try:
                    # Encontrar alguna guild donde el bot esté (asumimos la principal)
                    if not plugin.app.cache.get_guilds_view():
                        continue
                    
                    guild_id = list(plugin.app.cache.get_guilds_view().keys())[0]
                    member = plugin.app.cache.get_member(guild_id, discord_id) or await plugin.app.rest.fetch_member(guild_id, discord_id)
                    
                    for role_id in ban_roles:
                        if role_id in member.role_ids:
                            await member.remove_role(role_id, reason="Ban Expirado")
                            logger.info(f"[Bans] Rol quitado a {discord_id}")
                except Exception as e:
                    logger.error(f"[Bans] Error quitando rol a {discord_id}: {e}")
                    
    except Exception as e:
        logger.error(f"[Bans Task] Error verificando baneos expirados: {e}")
"""

if "check_expired_bans" not in content:
    content += new_task
    with open("apps/discord_bot/src/plugins/tasks.py", "w", encoding="utf-8") as f:
        f.write(content)
    print("Added check_expired_bans task")
