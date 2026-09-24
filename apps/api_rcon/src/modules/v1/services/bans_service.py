import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from fastapi import HTTPException
from sqlmodel import select, col
from sqlmodel.ext.asyncio.session import AsyncSession
from wardogs_schemas import v1 as schemas

from src.connections.databases.db import Ban, Player
from src.connections.apis.rcon import RCONManager
from src.connections.apis.steam import get_player_summary

logger = logging.getLogger("wardogs.bans")

class BansService:
    @staticmethod
    async def sync_bans(session: AsyncSession) -> Dict[str, Any]:
        try:
            active_servers = await RCONManager.get_all_active_servers(session)
            rcon_steam_ids: set[str] = set()
            for s_info, client in active_servers:
                try:
                    s_bans = await client.get_bans()
                    rcon_steam_ids.update(s_bans)
                except Exception as s_err:
                    logger.warning(f"Failed to fetch bans from {s_info.name} ({s_info.base_url}): {s_err}")
            
            stmt = select(Ban).where(Ban.is_active == True, Ban.rcon_sync_status != "DISCORD_ONLY")
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
                    
                new_ban = Ban(steam_id=sid, reason="", is_active=True, rcon_sync_status="SUCCESS")
                session.add(new_ban)
                db_steam_ids.add(sid)
                
            # 2. DB to RCON (Push our full combined list to all active servers)
            active_steam_ids = list(db_steam_ids)
            for s_info, client in active_servers:
                try:
                    await client.sync_banned_slots(active_steam_ids)
                except Exception as s_err:
                    logger.warning(f"Failed to push bans to {s_info.name} ({s_info.base_url}): {s_err}")
            
            # Mark pending DB bans as SUCCESS (excluding DISCORD_ONLY)
            for b in active_bans:
                if b.rcon_sync_status != "SUCCESS" and b.rcon_sync_status != "DISCORD_ONLY":
                    b.rcon_sync_status = "SUCCESS"
                    session.add(b)
                    
            await session.commit()
            
            return {"ok": True, "message": f"Bans synchronized successfully across {len(active_servers)} servers. Absorbed {len(missing_in_db)} from RCON."}
        except Exception as e:
            logger.error("Error synchronizing bans across servers", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    async def ban_player(steam_id: str, req: schemas.ReasonRequest, session: AsyncSession) -> Dict[str, Any]:
        reason = req.reason or "No reason provided"
        
        expires_at = None
        if req.duration_days and req.duration_days > 0:
            expires_at = datetime.now(timezone.utc) + timedelta(days=req.duration_days)

        player = await session.get(Player, steam_id)
        if not player:
            summary = await get_player_summary(steam_id)
            in_game_name = summary.get("personaname") if summary else "Unknown"
            avatar_url = summary.get("avatarfull") if summary else None
            
            player = Player(steam_id=steam_id, in_game_name=in_game_name, avatar_url=avatar_url)
            session.add(player)
            await session.flush()
            
        is_solo_discord = getattr(req, "solo_discord", False)
        status = "DISCORD_ONLY" if is_solo_discord else "PENDING"
        ban_entry = Ban(steam_id=steam_id, reason=reason, is_active=True, rcon_sync_status=status, expires_at=expires_at)
        session.add(ban_entry)
        await session.commit()
        
        if not is_solo_discord:
            active_servers = await RCONManager.get_all_active_servers(session)
            for s_info, client in active_servers:
                try:
                    await client.ban_player(steam_id, reason)
                except Exception as e:
                    logger.warning(f"Failed to execute real-time ban on {s_info.name}: {e}")
            
            await BansService.sync_bans(session)
        return {"ok": True}

    @staticmethod
    async def unban_player(steam_id: str, session: AsyncSession) -> Dict[str, Any]:
        stmt = select(Ban).where(Ban.steam_id == steam_id, Ban.is_active == True)
        active_bans = (await session.exec(stmt)).all()
        for b in active_bans:
            b.is_active = False
            session.add(b)
        await session.commit()
        
        await BansService.sync_bans(session)
        return {"ok": True}

    @staticmethod
    async def get_bans(steam_id: Optional[str], session: AsyncSession) -> schemas.DbBansResponse:
        stmt = select(Ban).where(Ban.is_active == True)
        if steam_id:
            stmt = stmt.where(Ban.steam_id == steam_id)
            
        bans = (await session.exec(stmt)).all()
        
        result = []
        for b in bans:
            result.append(schemas.DbBan(
                id=b.id or 0,
                steam_id=b.steam_id,
                reason=b.reason,
                is_active=b.is_active,
                banned_at=b.banned_at.isoformat() if b.banned_at else "",
                expires_at=b.expires_at.isoformat() if b.expires_at else None
            ))
            
        return schemas.DbBansResponse(bans=result)
