with open("apps/api_rcon/src/modules/v1/router.py", "r", encoding="utf-8") as f:
    content = f.read()

import re

old_sync = """@router.post("/db/sync_bans", dependencies=[Depends(verify_api_key_guard)])
async def sync_bans(session: AsyncSession = Depends(get_session)):
    try:
        # Get all active bans
        stmt = select(Ban).where(Ban.is_active == True)
        active_bans = (await session.exec(stmt)).all()
        
        active_steam_ids = list(set([b.steam_id for b in active_bans]))
        
        # Sync with RCON
        await rcon.sync_banned_slots(active_steam_ids)
        
        # Mark as SUCCESS
        for b in active_bans:
            if b.rcon_sync_status != "SUCCESS":
                b.rcon_sync_status = "SUCCESS"
                session.add(b)
        await session.commit()
        
        return {"ok": True, "message": "Bans synchronized successfully"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))"""

new_sync = """@router.post("/db/sync_bans", dependencies=[Depends(verify_api_key_guard)])
async def sync_bans(session: AsyncSession = Depends(get_session)):
    try:
        # Fetch bans from RCON directly
        rcon_bans_resp = await rcon.get_bans()
        rcon_steam_ids = set([b.steamId for b in rcon_bans_resp.bans if b.steamId]) if rcon_bans_resp.bans else set()
        
        # Get all active bans from DB
        stmt = select(Ban).where(Ban.is_active == True)
        active_bans = (await session.exec(stmt)).all()
        db_steam_ids = set([b.steam_id for b in active_bans])
        
        # 1. RCON to DB (Absorb missing bans)
        missing_in_db = rcon_steam_ids - db_steam_ids
        for sid in missing_in_db:
            player = await session.get(Player, sid)
            if not player:
                new_player = Player(steam_id=sid)
                session.add(new_player)
                await session.flush()
                
            new_ban = Ban(steam_id=sid, reason="Synced from RCON", is_active=True, rcon_sync_status="SUCCESS")
            session.add(new_ban)
            db_steam_ids.add(sid)
            
        # 2. DB to RCON (Push our full combined list)
        active_steam_ids = list(db_steam_ids)
        await rcon.sync_banned_slots(active_steam_ids)
        
        # Mark pending DB bans as SUCCESS
        for b in active_bans:
            if b.rcon_sync_status != "SUCCESS":
                b.rcon_sync_status = "SUCCESS"
                session.add(b)
                
        await session.commit()
        
        return {"ok": True, "message": f"Bans synchronized successfully. Absorbed {len(missing_in_db)} from RCON."}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))"""

content = content.replace(old_sync, new_sync)

with open("apps/api_rcon/src/modules/v1/router.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Updated router.py")
