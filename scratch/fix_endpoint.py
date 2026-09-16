with open("d:/proyectos_dev/matefield_bot/apps/api_rcon/src/connections/apis/rcon.py", "r", encoding="utf-8") as f:
    rcon_code = f.read()

# fix sync_reserved_slots
replacement_res = """        if insert_idx == -1:
            new_lines.append('')
            new_lines.append('[/Script/WDGame.WDGameSession]')
            insert_idx = len(new_lines) - 1
            
        if insert_idx != -1:"""
rcon_code = rcon_code.replace("        if insert_idx != -1:", replacement_res)

with open("d:/proyectos_dev/matefield_bot/apps/api_rcon/src/connections/apis/rcon.py", "w", encoding="utf-8") as f:
    f.write(rcon_code)

import re
with open("d:/proyectos_dev/matefield_bot/apps/api_rcon/src/modules/v1/router.py", "r", encoding="utf-8") as f:
    r_code = f.read()

def replace_ban_player(m):
    return """    reason = req.reason or "No reason provided"
    
    expires_at = None
    if req.duration_days and req.duration_days > 0:
        expires_at = datetime.now(timezone.utc) + timedelta(days=req.duration_days)

    # Save to historical db
    player = await session.get(Player, steam_id)
    if not player:
        # Create a stub player if they don't exist yet
        from src.connections.apis.steam import get_player_summary
        summary = await get_player_summary(steam_id)
        
        in_game_name = summary.get("personaname") if summary else "Unknown"
        avatar_url = summary.get("avatarfull") if summary else None
        
        player = Player(steam_id=steam_id, in_game_name=in_game_name, avatar_url=avatar_url)
        session.add(player)
        await session.flush()
        
    ban_entry = Ban(steam_id=steam_id, reason=reason, is_active=True, rcon_sync_status="PENDING", expires_at=expires_at)
    session.add(ban_entry)
    await session.commit()
    
    # Execute ban in live RCON
    try:
        await rcon.ban_player(steam_id, reason)
    except Exception as e:
        print(f"Failed to execute real-time ban: {e}")
    
    # Trigger sync
    await sync_bans(session)
    
    return {"ok": True}"""

r_code = re.sub(r'    reason = req\.reason or "No reason provided".*?return \{"ok": True\}', replace_ban_player, r_code, flags=re.DOTALL)

with open("d:/proyectos_dev/matefield_bot/apps/api_rcon/src/modules/v1/router.py", "w", encoding="utf-8") as f:
    f.write(r_code)

print("Applied endpoint and rcon fixes")
