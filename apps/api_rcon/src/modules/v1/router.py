from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Any, Optional
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy import func, desc, text
from datetime import datetime, timedelta, timezone

from wardogs_schemas import v1 as schemas

from src.security.guard import verify_api_key_guard
from src.connections.databases.db import (
    Player, Role, PlayerRole, Membership, PlayerSession, Ban, 
    Team, Match, MatchTeamStats, MatchPlayerStats, BotConfig, MembershipTypeConfig,
    get_session
)
from src.connections.apis.rcon import rcon_client as rcon

router = APIRouter(prefix="/v1", tags=["v1"])

@router.get("/status", dependencies=[Depends(verify_api_key_guard)], response_model=schemas.Status)
async def get_status():
    return await rcon.get_status()

@router.get("/steam/player/{steam_id}", dependencies=[Depends(verify_api_key_guard)])
async def get_steam_player(steam_id: str):
    from src.connections.apis.steam import get_player_summary
    data = await get_player_summary(steam_id)
    if not data:
        raise HTTPException(status_code=404, detail="Player not found in Steam")
    return data

@router.get("/players", dependencies=[Depends(verify_api_key_guard)], response_model=schemas.Players1)
async def get_players():
    return await rcon.get_players()

@router.get("/audit", dependencies=[Depends(verify_api_key_guard)], response_model=schemas.Audit)
async def get_audit_logs(limit: int = 50):
    return await rcon.get_audit_logs(limit)

@router.get("/reserved-slots", dependencies=[Depends(verify_api_key_guard)], response_model=schemas.ReservedSlots)
async def get_reserved_slots():
    return await rcon.get_reserved_slots()

@router.post("/reserved-slots", dependencies=[Depends(verify_api_key_guard)], response_model=schemas.Ok)
async def add_reserved_slot(req: schemas.SteamIdRequest):
    current = await rcon.get_reserved_slots()
    slots = set(current.reservedSlots or [])
    slots.add(req.steamId)
    await rcon.sync_reserved_slots(list(slots))
    return {"ok": True, "message": "Reserved slot added"}

@router.delete("/reserved-slots/{steam_id}", dependencies=[Depends(verify_api_key_guard)], response_model=schemas.Ok)
async def remove_reserved_slot(steam_id: str):
    current = await rcon.get_reserved_slots()
    slots = set(current.reservedSlots or [])
    if steam_id in slots:
        slots.remove(steam_id)
        await rcon.sync_reserved_slots(list(slots))
    return {"ok": True, "message": "Reserved slot removed"}

@router.post("/broadcast", dependencies=[Depends(verify_api_key_guard)], response_model=schemas.Ok)
async def broadcast(req: schemas.MessageRequest):
    await rcon.broadcast(req.message)
    return {"ok": True, "message": "Broadcast sent"}

@router.post("/players/{steam_id}/message", dependencies=[Depends(verify_api_key_guard)], response_model=schemas.Ok)
async def send_player_message(steam_id: str, req: schemas.MessageRequest):
    await rcon.send_player_message(steam_id, req.message)
    return {"ok": True}

@router.post("/players/{steam_id}/kick", dependencies=[Depends(verify_api_key_guard)], response_model=schemas.Ok)
async def kick_player(steam_id: str, req: schemas.ReasonRequest):
    await rcon.kick_player(steam_id, req.reason or "No reason provided")
    return {"ok": True}

@router.post("/db/sync_bans", dependencies=[Depends(verify_api_key_guard)])
async def sync_bans(session: AsyncSession = Depends(get_session)):
    try:
        # Fetch bans from RCON directly
        rcon_bans_resp = await rcon.get_bans()
        rcon_steam_ids = set(rcon_bans_resp)
        
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
                
            new_ban = Ban(steam_id=sid, reason="", is_active=True, rcon_sync_status="SUCCESS")
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
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/players/{steam_id}/ban", dependencies=[Depends(verify_api_key_guard)], response_model=schemas.Ok)
async def ban_player(steam_id: str, req: schemas.ReasonRequest, session: AsyncSession = Depends(get_session)):
    reason = req.reason or "No reason provided"
    
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
    
    return {"ok": True}

@router.post("/players/{steam_id}/unban", dependencies=[Depends(verify_api_key_guard)], response_model=schemas.Ok)
async def unban_player(steam_id: str, session: AsyncSession = Depends(get_session)):
    # Deactivate bans for this player
    stmt = select(Ban).where(Ban.steam_id == steam_id, Ban.is_active == True)
    active_bans = (await session.exec(stmt)).all()
    for b in active_bans:
        b.is_active = False
        session.add(b)
    await session.commit()
    
    # Trigger sync
    await sync_bans(session)
    
    return {"ok": True}

@router.post("/players/{steam_id}/faction", dependencies=[Depends(verify_api_key_guard)], response_model=schemas.Ok)
async def switch_faction(steam_id: str, req: schemas.FactionRequest):
    await rcon.switch_faction(steam_id, req.faction)
    return {"ok": True, "message": "Message sent"}

@router.get("/config", dependencies=[Depends(verify_api_key_guard)])
async def get_config():
    return await rcon.get_config()

class ConfigUpdateRequest(BaseModel):
    revision: str
    new_text: str

@router.put("/config", dependencies=[Depends(verify_api_key_guard)], response_model=schemas.ConfigResult)
async def update_config(req: ConfigUpdateRequest):
    return await rcon.update_config(req.revision, req.new_text)

# Database endpoints

class LinkAccountRequest(BaseModel):
    discord_id: str
    steam_id: str

@router.post("/db/players/link", dependencies=[Depends(verify_api_key_guard)], response_model=schemas.Ok)
async def link_account(req: LinkAccountRequest, session: AsyncSession = Depends(get_session)):
    player = await session.get(Player, req.steam_id)
    if not player:
        player = Player(steam_id=req.steam_id, discord_id=req.discord_id)
        session.add(player)
    else:
        player.discord_id = req.discord_id
    await session.commit()
    return {"ok": True, "message": "Account linked"}

@router.get("/db/players/discord/{discord_id}", dependencies=[Depends(verify_api_key_guard)])
async def get_player_by_discord(discord_id: str, session: AsyncSession = Depends(get_session)):
    statement = select(Player).where(Player.discord_id == discord_id)
    player = ((await session.exec(statement))).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    return {"steam_id": player.steam_id, "custom_welcome_message": player.custom_welcome_message}

@router.get("/db/players/steam/{steam_id}", dependencies=[Depends(verify_api_key_guard)])
async def get_player_by_steam(steam_id: str, session: AsyncSession = Depends(get_session)):
    player = await session.get(Player, steam_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
        
    now = datetime.now(timezone.utc)
    stmt = select(Membership).where(
        Membership.steam_id == steam_id,
        Membership.is_active == True
    )
    memberships = (await session.exec(stmt)).all()
    
    # Also fetch special roles
    stmt_roles = select(Role.name).join(PlayerRole).where(PlayerRole.steam_id == steam_id)
    special_roles = (await session.exec(stmt_roles)).all()
    
    active_roles = []
    active_memberships = []
    for m in memberships:
        if m.end_time is None or m.end_time > now:
            active_roles.append(m.membership_type.upper())
            active_memberships.append({
                "type": m.membership_type,
                "end_time": m.end_time.isoformat() if m.end_time else None,
                "rcon_sync_status": m.rcon_sync_status
            })
            
    # Add special roles to the active_roles list for primary role calculation
    for sr in special_roles:
        active_roles.append(sr.upper())
            
    primary_role = None
    if any("OWNER" in r for r in active_roles):
        primary_role = "OWNER"
    elif any("ADMIN" in r for r in active_roles):
        primary_role = "ADMIN"
    elif any("VIP" in r for r in active_roles):
        primary_role = "VIP"
    elif active_roles:
        primary_role = active_roles[0]
        
    return {
        "discord_id": player.discord_id, 
        "custom_welcome_message": player.custom_welcome_message,
        "active_role": primary_role,
        "memberships": active_memberships,
        "special_roles": special_roles
    }

@router.get("/db/players/steam/{steam_id}/stats", dependencies=[Depends(verify_api_key_guard)])
async def get_player_stats_by_steam(steam_id: str, session: AsyncSession = Depends(get_session)):
    # Get match stats
    statement = (
        select(
            func.sum(MatchPlayerStats.kills).label("total_kills"),
            func.sum(MatchPlayerStats.deaths).label("total_deaths"),
            func.sum(MatchPlayerStats.cash_earned).label("total_cash_earned"),
            func.count(text('1')).label("matches_played")
        )
        .where(MatchPlayerStats.steam_id == steam_id)
    )
    result = ((await session.exec(statement))).first()
    
    # Get playtime
    playtime_stmt = select(func.sum(PlayerSession.total_seconds)).where(PlayerSession.steam_id == steam_id)
    playtime_result = (await session.exec(playtime_stmt)).first()
    total_playtime_seconds = int(playtime_result or 0)
    
    return {
        "total_kills": int(result[0] or 0) if result else 0,
        "total_deaths": int(result[1] or 0) if result else 0,
        "total_cash_earned": int(result[2] or 0) if result else 0,
        "matches_played": int(result[3] or 0) if result else 0,
        "total_playtime_seconds": total_playtime_seconds
    }

@router.post("/db/players/steam/{steam_id}/welcome-message", dependencies=[Depends(verify_api_key_guard)], response_model=schemas.Ok)
async def set_welcome_message(steam_id: str, req: schemas.MessageRequest, session: AsyncSession = Depends(get_session)):
    player = await session.get(Player, steam_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    
    # Note: RBAC validation to check if they have VIP/ADMIN should happen here
    player.custom_welcome_message = req.message
    session.add(player)
    await session.commit()
    return {"ok": True, "message": "Welcome message updated"}

class AddMembershipRequest(BaseModel):
    steam_id: str
    membership_type: str
    days: Optional[int] = None
    special_role: Optional[str] = None

class EditMembershipRequest(BaseModel):
    days: Optional[int] = None
    add_days: Optional[int] = None
    membership_type: Optional[str] = None
    is_active: Optional[bool] = None

class EditPlayerRequest(BaseModel):
    discord_id: Optional[str] = None
    custom_welcome_message: Optional[str] = None
    observations: Optional[str] = None

@router.post("/db/players/membership", dependencies=[Depends(verify_api_key_guard)], response_model=schemas.Ok)
async def add_membership(req: AddMembershipRequest, session: AsyncSession = Depends(get_session)):
    player = await session.get(Player, req.steam_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    
    if req.days is None:
        config_key = f"ROLE_DAYS_{req.membership_type.upper()}"
        config_days = (await session.exec(select(BotConfig).where(BotConfig.config_key == config_key))).first()
        days_to_add = int(config_days.config_value) if config_days else 30
    else:
        days_to_add = req.days

    # Check quota if it's a new membership or one that's inactive
    config = (await session.exec(select(MembershipTypeConfig).where(MembershipTypeConfig.membership_type == req.membership_type.upper()))).first()
    if config and config.max_quota is not None:
        usage_stmt = select(func.count(Membership.id)).where(Membership.membership_type == req.membership_type.upper(), Membership.is_active == True) # type: ignore
        current_usage = (await session.exec(usage_stmt)).one()
        
        # If player already has this membership active, it doesn't count as a new slot
        existing_active = (await session.exec(
            select(Membership).where(
                Membership.steam_id == req.steam_id,
                Membership.membership_type == req.membership_type,
                Membership.is_active == True
            )
        )).first()
        
        if not existing_active and current_usage >= config.max_quota:
            raise HTTPException(status_code=400, detail=f"No hay cupos disponibles para la membresía tipo {req.membership_type.upper()}. Límite de {config.max_quota} alcanzado.")

    start_date = datetime.now(timezone.utc)
    
    end_date = start_date + timedelta(days=days_to_add) if days_to_add > 0 else None

    # Check for existing active membership
    existing_membership = (await session.exec(
        select(Membership).where(
            Membership.steam_id == req.steam_id,
            Membership.membership_type == req.membership_type,
            Membership.is_active == True
        )
    )).first()

    if existing_membership:
        if existing_membership.end_time:
            if existing_membership.end_time > start_date:
                # Still active, accumulate remaining time to the new membership
                remaining_time = existing_membership.end_time - start_date
                end_date = start_date + remaining_time + timedelta(days=days_to_add) if days_to_add > 0 else None
                
        # Expire the old membership to keep history intact
        existing_membership.is_active = False
        existing_membership.end_time = start_date # Mark it as ended now
        session.add(existing_membership)
    
    membership = Membership(
        steam_id=req.steam_id,
        membership_type=req.membership_type,
        start_time=start_date,
        end_time=end_date,
        is_active=True
    )
    
    if req.special_role:
        role = (await session.exec(select(Role).where(Role.name == req.special_role))).first()
        if not role:
            role = Role(name=req.special_role)
            session.add(role)
            await session.commit()
            await session.refresh(role)
            
        membership.special_role_id = role.id
            
        player_role = (await session.exec(select(PlayerRole).where(PlayerRole.steam_id == req.steam_id, PlayerRole.role_id == role.id))).first()
        if not player_role:
            assert role.id is not None
            player_role = PlayerRole(steam_id=req.steam_id, role_id=role.id)
            session.add(player_role)
            
    session.add(membership)
    await session.commit()
    return {"ok": True, "message": "Membership added"}

@router.put("/db/memberships/{membership_id}", dependencies=[Depends(verify_api_key_guard)], response_model=schemas.Ok)
async def edit_membership(membership_id: int, req: EditMembershipRequest, session: AsyncSession = Depends(get_session)):
    membership = await session.get(Membership, membership_id)
    if not membership:
        raise HTTPException(status_code=404, detail="Membership not found")
        
    if req.membership_type is not None:
        membership.membership_type = req.membership_type
        
    if req.days is not None:
        if req.days == 0:
            membership.end_time = None
        else:
            membership.end_time = membership.start_time + timedelta(days=req.days)
            
    if req.add_days is not None:
        if membership.end_time is not None:
            membership.end_time = membership.end_time + timedelta(days=req.add_days)
            
    if req.is_active is not None:
        membership.is_active = req.is_active
        if not req.is_active and membership.special_role_id:
            other_active = (await session.exec(select(Membership).where(
                Membership.steam_id == membership.steam_id,
                Membership.special_role_id == membership.special_role_id,
                Membership.is_active == True,
                Membership.id != membership.id
            ))).first()
            if not other_active:
                pr = (await session.exec(select(PlayerRole).where(
                    PlayerRole.steam_id == membership.steam_id,
                    PlayerRole.role_id == membership.special_role_id
                ))).first()
                if pr:
                    await session.delete(pr)
                    
    session.add(membership)
    await session.commit()
    return {"ok": True, "message": "Membership updated"}

class CompensateRequest(BaseModel):
    days: int

@router.post("/db/memberships/compensate", dependencies=[Depends(verify_api_key_guard)], response_model=schemas.Ok)
async def compensate_memberships(req: CompensateRequest, session: AsyncSession = Depends(get_session)):
    # Find all active memberships that have an end_time (not infinite)
    stmt = select(Membership).where(Membership.is_active == True, Membership.end_time != None)
    active_memberships = (await session.exec(stmt)).all()
    
    count = 0
    for m in active_memberships:
        m.end_time = m.end_time + timedelta(days=req.days) # type: ignore
        session.add(m)
        count += 1
        
    await session.commit()
    return {"ok": True, "message": f"Compensated {count} memberships with {req.days} days."}

@router.delete("/db/memberships/{membership_id}", dependencies=[Depends(verify_api_key_guard)], response_model=schemas.Ok)
async def delete_membership(membership_id: int, session: AsyncSession = Depends(get_session)):
    membership = await session.get(Membership, membership_id)
    if not membership:
        raise HTTPException(status_code=404, detail="Membership not found")
        
    if membership.special_role_id:
        other_active = (await session.exec(select(Membership).where(
            Membership.steam_id == membership.steam_id,
            Membership.special_role_id == membership.special_role_id,
            Membership.is_active == True,
            Membership.id != membership.id
        ))).first()
        if not other_active:
            pr = (await session.exec(select(PlayerRole).where(
                PlayerRole.steam_id == membership.steam_id,
                PlayerRole.role_id == membership.special_role_id
            ))).first()
            if pr:
                await session.delete(pr)

    await session.delete(membership)
    await session.commit()
    return {"ok": True, "message": "Membership deleted"}

@router.post("/db/players/{steam_id}/roles/{role_id}", dependencies=[Depends(verify_api_key_guard)], response_model=schemas.Ok)
async def add_special_role(steam_id: str, role_id: str, session: AsyncSession = Depends(get_session)):
    player = await session.get(Player, steam_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
        
    role = (await session.exec(select(Role).where(Role.name == role_id))).first()
    if not role:
        role = Role(name=role_id)
        session.add(role)
        await session.commit()
        await session.refresh(role)
        
    player_role = (await session.exec(select(PlayerRole).where(PlayerRole.steam_id == steam_id, PlayerRole.role_id == role.id))).first()
    if player_role:
        return {"ok": True, "message": "Player already has this role"}
        
    assert role.id is not None
    player_role = PlayerRole(steam_id=steam_id, role_id=role.id)
    session.add(player_role)
    await session.commit()
    return {"ok": True, "message": "Role added to player"}

@router.delete("/db/players/{steam_id}/roles/{role_id}", dependencies=[Depends(verify_api_key_guard)], response_model=schemas.Ok)
async def remove_special_role(steam_id: str, role_id: str, session: AsyncSession = Depends(get_session)):
    role = (await session.exec(select(Role).where(Role.name == role_id))).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
        
    player_role = (await session.exec(select(PlayerRole).where(PlayerRole.steam_id == steam_id, PlayerRole.role_id == role.id))).first()
    if not player_role:
        raise HTTPException(status_code=404, detail="Player does not have this role")
        
    await session.delete(player_role)
    await session.commit()
    return {"ok": True, "message": "Role removed from player"}

@router.put("/db/players/{steam_id}", dependencies=[Depends(verify_api_key_guard)], response_model=schemas.Ok)
async def edit_player(steam_id: str, req: EditPlayerRequest, session: AsyncSession = Depends(get_session)):
    player = await session.get(Player, steam_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
        
    if req.discord_id is not None:
        player.discord_id = req.discord_id if req.discord_id else None
        
    if req.custom_welcome_message is not None:
        player.custom_welcome_message = req.custom_welcome_message if req.custom_welcome_message else None
        
    if req.observations is not None:
        player.observations = req.observations if req.observations else None
        
    await session.commit()
    return {"ok": True, "message": "Player updated"}

class UnlinkAccountRequest(BaseModel):
    discord_id: str

@router.post("/db/players/unlink", dependencies=[Depends(verify_api_key_guard)], response_model=schemas.Ok)
async def unlink_account(req: UnlinkAccountRequest, session: AsyncSession = Depends(get_session)):
    statement = select(Player).where(Player.discord_id == req.discord_id)
    player = ((await session.exec(statement))).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found for this Discord ID")
    
    player.discord_id = None
    session.add(player)
    await session.commit()
    return {"ok": True, "message": "Account unlinked successfully"}

import csv
import io
from fastapi.responses import StreamingResponse
from src.connections.databases.db import (
    Role, PlayerRole, Membership, Team, Match, MatchTeamStats, MatchPlayerStats
)

@router.get("/db/export/{table_name}", dependencies=[Depends(verify_api_key_guard)])
async def export_table_csv(table_name: str, session: AsyncSession = Depends(get_session)):
    table_map = {
        "players": Player,
        "roles": Role,
        "player_roles": PlayerRole,
        "memberships": Membership,
        "teams": Team,
        "matches": Match,
        "match_team_stats": MatchTeamStats,
        "match_player_stats": MatchPlayerStats
    }
    
    if table_name not in table_map:
        raise HTTPException(status_code=404, detail="Table not found")
        
    model = table_map[table_name]
    records = (await session.exec(select(model))).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    if not records:
        # Write only headers if table is empty
        headers = list(model.model_fields.keys())
        writer.writerow(headers)
    else:
        # Write headers and data
        headers = list(records[0].model_dump().keys())
        writer.writerow(headers)
        for record in records:
            writer.writerow(list(record.model_dump().values()))
            
    output.seek(0)
    
    return StreamingResponse(
        output, 
        media_type="text/csv", 
        headers={"Content-Disposition": f'attachment; filename="{table_name}.csv"'}
    )

@router.get("/db/leaderboard", dependencies=[Depends(verify_api_key_guard)])
async def get_db_leaderboard(metric: str = "kills", limit: int = 15, session: AsyncSession = Depends(get_session)):
    valid_metrics = {
        "kills": MatchPlayerStats.kills, 
        "deaths": MatchPlayerStats.deaths, 
        "cash_earned": MatchPlayerStats.cash_earned
    }
    
    if metric not in valid_metrics:
        raise HTTPException(status_code=400, detail="Invalid metric")
        
    metric_col = valid_metrics[metric]
    
    statement = (
        select(MatchPlayerStats.steam_id, Player.discord_id, func.sum(metric_col).label("total"))
        .join(Player, MatchPlayerStats.steam_id == Player.steam_id)  # type: ignore
        .group_by(MatchPlayerStats.steam_id, Player.discord_id)      # type: ignore
        .order_by(func.sum(metric_col).desc())
        .limit(limit)
    )
    
    results = ((await session.exec(statement))).all()
    
    return {
        "metric": metric,
        "leaderboard": [
            {"steam_id": row[0], "discord_id": row[1], "total": int(row[2]) if row[2] else 0}
            for row in results
        ]
    }

@router.post("/db/sync_memberships", dependencies=[Depends(verify_api_key_guard)])
async def sync_memberships(session: AsyncSession = Depends(get_session)):
    now = datetime.now(timezone.utc)
    
    # 1. Expire old memberships
    expired_stmt = select(Membership).where(
        Membership.is_active == True,
        Membership.end_time != None,
        Membership.end_time < now  # type: ignore
    )
    expired = ((await session.exec(expired_stmt))).all()
    for m in expired:
        m.is_active = False
        session.add(m)
                    
    if expired:
        await session.commit()
        
    # 2. Get active steam_ids
    active_stmt = select(Membership.steam_id).where(Membership.is_active == True).distinct()
    active_steam_ids = set(((await session.exec(active_stmt))).all())
    
    # 3. Sync RCON
    try:
        # Sincronizamos la lista completa de steam_ids activos
        await rcon.sync_reserved_slots(list(active_steam_ids))
        
        # Marcamos todos los activos como SUCCESS en la base de datos
        for sid in active_steam_ids:
            m_stmt = select(Membership).where(Membership.steam_id == sid, Membership.is_active == True)
            for m in (await session.exec(m_stmt)).all():
                if m.rcon_sync_status != "SUCCESS":
                    m.rcon_sync_status = "SUCCESS"
                    session.add(m)
        await session.commit()
        
    except Exception as e:
        print(f"Failed to sync RCON reserved slots: {e}")
        
    # 4. Prepare data for Discord Bot Role Sync
    players_stmt = select(Player).where(Player.discord_id != None)
    players = ((await session.exec(players_stmt))).all()
    
    discord_sync_data = []
    for p in players:
        m_stmt = select(Membership.membership_type).where(Membership.steam_id == p.steam_id, Membership.is_active == True)
        m_types = ((await session.exec(m_stmt))).all()
        
        pr_stmt = select(PlayerRole.role_id).where(PlayerRole.steam_id == p.steam_id)
        p_roles = ((await session.exec(pr_stmt))).all()
        special_roles = []
        for r_id in p_roles:
            r = await session.get(Role, r_id)
            if r and r.name and r.name.isdigit(): # If it's a discord role ID
                special_roles.append(int(r.name))
        
        discord_sync_data.append({
            "discord_id": p.discord_id,
            "active_memberships": list(m_types),
            "special_roles": special_roles
        })
        
    configs = (await session.exec(select(BotConfig).where(BotConfig.config_key.startswith("ROLE_MAP_")))).all()
    role_maps = {c.config_key.replace("ROLE_MAP_", ""): int(c.config_value) for c in configs}
    
    all_roles = (await session.exec(select(Role))).all()
    managed_special_roles = []
    for r in all_roles:
        if r.name and r.name.isdigit():
            managed_special_roles.append(int(r.name))
        
    return {
        "sync_data": discord_sync_data, 
        "role_maps": role_maps,
        "managed_special_roles": managed_special_roles
    }

@router.get("/db/rcon_sync_status", dependencies=[Depends(verify_api_key_guard)])
async def rcon_sync_status(session: AsyncSession = Depends(get_session)):
    # 1. Get active steam_ids from DB
    active_stmt = select(Membership.steam_id).where(Membership.is_active == True).distinct()
    active_steam_ids = set(((await session.exec(active_stmt))).all())
    
    # 2. Get current reserved slots from RCON
    try:
        current_slots_resp = await rcon.get_reserved_slots()
        current_slots = set(current_slots_resp.reservedSlots or [])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch from RCON: {e}")
    
    # 3. Calculate differences
    synced = list(active_steam_ids.intersection(current_slots))
    pending_add = list(active_steam_ids - current_slots)
    pending_remove = list(current_slots - active_steam_ids)
    
    return {
        "synced": synced,
        "pending_add": pending_add,
        "pending_remove": pending_remove
    }

class SetBotConfigRequest(BaseModel):
    key: str
    value: str

@router.get("/bot/config/{key}", dependencies=[Depends(verify_api_key_guard)])
async def get_bot_config(key: str, session: AsyncSession = Depends(get_session)):
    config = await session.get(BotConfig, key)
    if not config:
        raise HTTPException(status_code=404, detail="Config key not found")
    return {"key": config.config_key, "value": config.config_value}

@router.put("/bot/config", dependencies=[Depends(verify_api_key_guard)], response_model=schemas.Ok)
async def set_bot_config(req: SetBotConfigRequest, session: AsyncSession = Depends(get_session)):
    config = await session.get(BotConfig, req.key)
    if not config:
        config = BotConfig(config_key=req.key, config_value=req.value)
        session.add(config)
    else:
        config.config_value = req.value
    await session.commit()
    return {"ok": True, "message": "Config updated"}

@router.delete("/bot/config/{key}", dependencies=[Depends(verify_api_key_guard)], response_model=schemas.Ok)
async def delete_bot_config(key: str, session: AsyncSession = Depends(get_session)):
    config = await session.get(BotConfig, key)
    if config:
        await session.delete(config)
        await session.commit()
    return {"ok": True, "message": "Config deleted"}

@router.get("/bot/configs", dependencies=[Depends(verify_api_key_guard)])
async def get_all_bot_configs(session: AsyncSession = Depends(get_session)):
    configs = (await session.exec(select(BotConfig))).all()
    return {"configs": {c.config_key: c.config_value for c in configs}}

@router.get("/db/memberships", dependencies=[Depends(verify_api_key_guard)])
async def get_paginated_memberships(page: int = 1, limit: int = 10, session: AsyncSession = Depends(get_session)):
    offset = (page - 1) * limit
    statement = select(Membership).order_by(Membership.start_time.desc()).offset(offset).limit(limit)  # type: ignore
    memberships = ((await session.exec(statement))).all()
    
    total_statement = select(func.count(Membership.id))  # type: ignore
    total = ((await session.exec(total_statement))).one()
    
    results = []
    for m in memberships:
        special_role_name = None
        if m.special_role_id:
            r = await session.get(Role, m.special_role_id)
            if r:
                special_role_name = r.name
        
        results.append({
            "id": m.id,
            "steam_id": m.steam_id,
            "type": m.membership_type,
            "is_active": m.is_active,
            "start_date": m.start_time.isoformat(),
            "end_date": m.end_time.isoformat() if m.end_time else None,
            "special_role": special_role_name
        })
    
    return {
        "page": page,
        "limit": limit,
        "total": total,
        "memberships": results
    }

@router.get("/db/players", dependencies=[Depends(verify_api_key_guard)])
async def get_paginated_players(page: int = 1, limit: int = 10, linked: str = "all", session: AsyncSession = Depends(get_session)):
    # Base query for DB players
    statement = select(Player)
            
    if linked == "linked":
        statement = statement.where(Player.discord_id != None)
    elif linked == "unlinked":
        statement = statement.where(Player.discord_id == None)
        
    # Get total count
    total_statement = select(func.count(Player.steam_id)) # type: ignore
    if linked == "linked":
        total_statement = total_statement.where(Player.discord_id != None)
    elif linked == "unlinked":
        total_statement = total_statement.where(Player.discord_id == None)
    total = ((await session.exec(total_statement))).one()
    
    # Sort and paginate
    offset = (page - 1) * limit
    statement = statement.order_by(Player.steam_id).offset(offset).limit(limit)
    db_players = ((await session.exec(statement))).all()
    
    paginated_results = []
    
    from src.connections.apis.steam import get_player_summary
    import asyncio
    
    # Add DB players
    for p in db_players:
        paginated_results.append({
            "steam_id": p.steam_id,
            "discord_id": p.discord_id,
            "is_online": False, # No longer tracking online status in /db
            "is_linked": p.discord_id is not None,
            "name": "Sin Nickname"
        })
        
    # Fetch steam names in parallel
    async def fetch_name(p):
        summary = await get_player_summary(p["steam_id"])
        if summary and "personaname" in summary:
            p["name"] = summary["personaname"]
            
    await asyncio.gather(*(fetch_name(p) for p in paginated_results))

    
    # Attach memberships
    for p in paginated_results:
        if p["is_linked"]:
            mem_stmt = select(Membership).where(Membership.steam_id == p["steam_id"], Membership.is_active == True)
            membership = ((await session.exec(mem_stmt))).first()
            p["vip_type"] = membership.membership_type if membership else None
            p["special_role"] = None
            if membership and membership.special_role_id:
                r = await session.get(Role, membership.special_role_id)
                if r:
                    p["special_role"] = r.name
        else:
            p["vip_type"] = None
            p["special_role"] = None
            
    return {
        "page": page,
        "limit": limit,
        "total": total,
        "players": paginated_results
    }

@router.get("/db/matches", dependencies=[Depends(verify_api_key_guard)])
async def get_paginated_matches(page: int = 1, limit: int = 10, session: AsyncSession = Depends(get_session)):
    offset = (page - 1) * limit
    statement = select(Match).order_by(Match.start_time.desc()).offset(offset).limit(limit)  # type: ignore
    matches = ((await session.exec(statement))).all()
    
    total_statement = select(func.count(Match.id))  # type: ignore
    total = ((await session.exec(total_statement))).one()
    
    return {
        "page": page,
        "limit": limit,
        "total": total,
        "matches": [
            {
                "id": m.id, 
                "map": m.map_name, 
                "start_time": m.start_time.isoformat(),
                "end_time": m.end_time.isoformat() if m.end_time else None
            } 
            for m in matches
        ]
    }

@router.get("/db/matches/latest", dependencies=[Depends(verify_api_key_guard)])
async def get_latest_match(session: AsyncSession = Depends(get_session)):
    # Get the most recently ended match
    statement = select(Match).where(Match.end_time != None).order_by(desc(Match.end_time))  # type: ignore
    match = (await session.exec(statement)).first()
    
    if not match:
        raise HTTPException(status_code=404, detail="No completed matches found")
        
    team_stats_stmt = select(MatchTeamStats, Team).join(Team).where(MatchTeamStats.match_id == match.id)
    team_stats = (await session.exec(team_stats_stmt)).all()
    
    player_stats_stmt = select(MatchPlayerStats).where(MatchPlayerStats.match_id == match.id)
    player_stats = (await session.exec(player_stats_stmt)).all()
    
    return {
        "id": match.id,
        "map": match.map_name,
        "start_time": match.start_time.isoformat(),
        "end_time": match.end_time.isoformat() if match.end_time else None,
        "winning_team_id": match.winning_team_id,
        "team_stats": [
            {
                "team_id": ts.team_id,
                "team_name": team.name,
                "team_code": team.code,
                "score": ts.score
            }
            for ts, team in team_stats
        ],
        "player_stats": [
            {
                "steam_id": ps.steam_id,
                "team_id": ps.team_id,
                "kills": ps.kills,
                "deaths": ps.deaths,
                "cash_earned": ps.cash_earned
            }
            for ps in player_stats
        ]
    }

from pydantic import BaseModel
class QuotaUpdateRequest(BaseModel):
    max_quota: Optional[int]

@router.get("/db/quotas", dependencies=[Depends(verify_api_key_guard)])
async def get_quotas(session: AsyncSession = Depends(get_session)):
    configs = (await session.exec(select(MembershipTypeConfig))).all()
    
    # Calculate current usage
    usage_stmt = select(Membership.membership_type, func.count(Membership.id)).where(Membership.is_active == True).group_by(Membership.membership_type) # type: ignore
    usage = (await session.exec(usage_stmt)).all()
    usage_dict = {t: c for t, c in usage}
    
    result = []
    for c in configs:
        result.append({
            "membership_type": c.membership_type,
            "max_quota": c.max_quota,
            "current_usage": usage_dict.get(c.membership_type, 0)
        })
        
    return {"quotas": result}

@router.put("/db/quotas/{membership_type}", dependencies=[Depends(verify_api_key_guard)])
async def update_quota(membership_type: str, request: QuotaUpdateRequest, session: AsyncSession = Depends(get_session)):
    config = (await session.exec(select(MembershipTypeConfig).where(MembershipTypeConfig.membership_type == membership_type))).first()
    
    if not config:
        config = MembershipTypeConfig(membership_type=membership_type, max_quota=request.max_quota)
        session.add(config)
    else:
        config.max_quota = request.max_quota
        session.add(config)
        
    await session.commit()
    
    return {"success": True, "membership_type": membership_type, "max_quota": request.max_quota}

@router.get("/steam/players", dependencies=[Depends(verify_api_key_guard)])
async def get_steam_players_batch(steam_ids: str):
    from src.connections.apis.steam import get_player_summaries
    ids_list = [sid.strip() for sid in steam_ids.split(",") if sid.strip()]
    if not ids_list:
        return {}
    return await get_player_summaries(ids_list)

@router.get("/db/bans", dependencies=[Depends(verify_api_key_guard)], response_model=schemas.DbBansResponse)
async def get_db_bans(steam_id: Optional[str] = None, session: AsyncSession = Depends(get_session)):
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
