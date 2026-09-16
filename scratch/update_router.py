with open("apps/api_rcon/src/modules/v1/router.py", "r", encoding="utf-8") as f:
    content = f.read()

import re

# Update ban_player
old_ban_player = """@router.post("/players/{steam_id}/ban", dependencies=[Depends(verify_api_key_guard)], response_model=schemas.Ok)
async def ban_player(steam_id: str, req: schemas.ReasonRequest, session: AsyncSession = Depends(get_session)):
    reason = req.reason or "No reason provided"
    
    ban_entry = Ban(steam_id=steam_id, reason=reason, is_active=True, rcon_sync_status="PENDING")
    session.add(ban_entry)"""

new_ban_player = """@router.post("/players/{steam_id}/ban", dependencies=[Depends(verify_api_key_guard)], response_model=schemas.Ok)
async def ban_player(steam_id: str, req: schemas.ReasonRequest, session: AsyncSession = Depends(get_session)):
    import datetime
    reason = req.reason or "No reason provided"
    
    expires_at = None
    if req.duration_days and req.duration_days > 0:
        expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=req.duration_days)
    
    # Check if a ban already exists
    stmt = select(Ban).where(Ban.steam_id == steam_id, Ban.is_active == True)
    existing_ban = (await session.exec(stmt)).first()
    
    if existing_ban:
        existing_ban.reason = reason
        existing_ban.expires_at = expires_at
        existing_ban.rcon_sync_status = "PENDING"
    else:
        ban_entry = Ban(steam_id=steam_id, reason=reason, is_active=True, rcon_sync_status="PENDING", expires_at=expires_at)
        session.add(ban_entry)"""

content = content.replace(old_ban_player, new_ban_player)

# Update get_db_bans
old_get_db_bans = """    for b in bans:
        result.append(schemas.DbBan(
            id=b.id,
            steam_id=b.steam_id,
            reason=b.reason,
            is_active=b.is_active,
            banned_at=b.banned_at.isoformat() if b.banned_at else ""
        ))"""

new_get_db_bans = """    for b in bans:
        result.append(schemas.DbBan(
            id=b.id,
            steam_id=b.steam_id,
            reason=b.reason,
            is_active=b.is_active,
            banned_at=b.banned_at.isoformat() if b.banned_at else "",
            expires_at=b.expires_at.isoformat() if b.expires_at else None
        ))"""

content = content.replace(old_get_db_bans, new_get_db_bans)

with open("apps/api_rcon/src/modules/v1/router.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Updated router.py")
