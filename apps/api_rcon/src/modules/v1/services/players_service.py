import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import HTTPException
from sqlmodel import select, func, text, col
from sqlmodel.ext.asyncio.session import AsyncSession

from src.connections.databases.db import Player, Membership, Role, PlayerRole, MatchPlayerStats, PlayerSession
from src.connections.apis.steam import get_player_summary, get_player_summaries
from src.modules.v1.schemas.dtos import LinkAccountRequest, UnlinkAccountRequest, EditPlayerRequest

class PlayersService:
    @staticmethod
    async def link_account(req: LinkAccountRequest, session: AsyncSession) -> Dict[str, Any]:
        # 1. Validar que el SteamID no esté ya vinculado a otra cuenta de Discord
        player = await session.get(Player, req.steam_id)
        if player and player.discord_id and player.discord_id != req.discord_id:
            raise HTTPException(
                status_code=400,
                detail=f"El Steam ID '{req.steam_id}' ya está vinculado a otra cuenta de Discord."
            )

        # 2. Validar que esta cuenta de Discord no esté ya vinculada a otro SteamID
        existing_discord = (await session.exec(
            select(Player).where(Player.discord_id == req.discord_id)
        )).first()
        if existing_discord and existing_discord.steam_id != req.steam_id:
            raise HTTPException(
                status_code=400,
                detail=f"Tu cuenta de Discord ya está vinculada al Steam ID '{existing_discord.steam_id}'. Usa /player unlink primero."
            )

        if not player:
            player = Player(steam_id=req.steam_id, discord_id=req.discord_id)
            session.add(player)
        else:
            player.discord_id = req.discord_id
            session.add(player)
        await session.commit()
        return {"ok": True, "message": "Account linked"}

    @staticmethod
    async def unlink_account(req: UnlinkAccountRequest, session: AsyncSession) -> Dict[str, Any]:
        statement = select(Player).where(Player.discord_id == req.discord_id)
        player = (await session.exec(statement)).first()
        if not player:
            raise HTTPException(status_code=404, detail="No se encontró ningún jugador vinculado a esta cuenta de Discord.")
        player.discord_id = None
        session.add(player)
        await session.commit()
        return {"ok": True, "message": "Account unlinked successfully"}

    @staticmethod
    async def get_by_discord(discord_id: str, session: AsyncSession) -> Dict[str, Any]:
        statement = select(Player).where(Player.discord_id == discord_id)
        player = (await session.exec(statement)).first()
        if not player:
            raise HTTPException(status_code=404, detail="Player not found")
        return {
            "steam_id": player.steam_id,
            "custom_welcome_message": player.custom_welcome_message,
            "observations": player.observations,
        }

    @staticmethod
    async def get_by_steam(steam_id: str, session: AsyncSession) -> Dict[str, Any]:
        player = await session.get(Player, steam_id)
        if not player:
            raise HTTPException(status_code=404, detail="Player not found")
            
        now = datetime.now(timezone.utc)
        stmt = select(Membership).where(
            Membership.steam_id == steam_id,
            Membership.is_active == True
        )
        memberships = (await session.exec(stmt)).all()
        
        # Fetch special roles (DDD)
        stmt_roles = select(Role).join(PlayerRole).where(PlayerRole.steam_id == steam_id)
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
                
        # Semantic evaluation: SYSTEM roles map to ADMIN (no isolated owner)
        for sr in special_roles:
            if sr.role_type == "SYSTEM":
                active_roles.append("ADMIN")
            elif sr.role_type == "VIP":
                active_roles.append("VIP")
            else:
                active_roles.append(sr.code)
                
        primary_role = None
        if any(r in ("ADMIN", "OWNER", "SUPERVISOR") for r in active_roles):
            primary_role = "ADMIN"
        elif any("VIP" in r for r in active_roles):
            primary_role = "VIP"
        elif active_roles:
            primary_role = active_roles[0]
            


        return {
            "name": player.in_game_name,
            "in_game_name": player.in_game_name,
            "avatar_url": player.avatar_url,
            "discord_id": player.discord_id, 
            "custom_welcome_message": player.custom_welcome_message,
            "observations": player.observations,
            "active_role": primary_role,
            "memberships": active_memberships,
            "active_memberships": active_memberships,
            "special_roles": [r.code for r in special_roles]
        }

    @staticmethod
    async def get_stats(steam_id: str, session: AsyncSession) -> Dict[str, Any]:
        statement = (
            select(
                func.sum(MatchPlayerStats.kills).label("total_kills"),
                func.sum(MatchPlayerStats.deaths).label("total_deaths"),
                func.sum(MatchPlayerStats.cash_earned).label("total_cash_earned"),
                func.count(text("1")).label("matches_played")
            )
            .where(MatchPlayerStats.steam_id == steam_id)
        )
        result = (await session.exec(statement)).first()
        
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

    @staticmethod
    async def edit_player(steam_id: str, req: EditPlayerRequest, session: AsyncSession) -> Dict[str, Any]:
        player = await session.get(Player, steam_id)
        if not player:
            raise HTTPException(status_code=404, detail="Player not found")
            
        if req.discord_id is not None:
            if req.discord_id:
                existing = (await session.exec(select(Player).where(Player.discord_id == req.discord_id))).first()
                if existing and existing.steam_id != steam_id:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Esta cuenta de Discord ya está vinculada al Steam ID '{existing.steam_id}'."
                    )
                player.discord_id = req.discord_id
            else:
                player.discord_id = None
        if req.custom_welcome_message is not None:
            player.custom_welcome_message = req.custom_welcome_message if req.custom_welcome_message else None
        if req.observations is not None:
            player.observations = req.observations if req.observations else None
            
        session.add(player)
        await session.commit()
        return {"ok": True, "message": "Player updated"}

    @staticmethod
    async def set_welcome_message(steam_id: str, message: str, session: AsyncSession) -> Dict[str, Any]:
        player = await session.get(Player, steam_id)
        if not player:
            raise HTTPException(status_code=404, detail="Player not found")
        player.custom_welcome_message = message
        session.add(player)
        await session.commit()
        return {"ok": True, "message": "Welcome message updated"}

    @staticmethod
    async def get_paginated_players(page: int, limit: int, linked: str, session: AsyncSession) -> Dict[str, Any]:
        statement = select(Player)
        if linked == "linked":
            statement = statement.where(Player.discord_id != None)
        elif linked == "unlinked":
            statement = statement.where(Player.discord_id == None)
            
        total_statement = select(func.count(col(Player.steam_id)))
        if linked == "linked":
            total_statement = total_statement.where(Player.discord_id != None)
        elif linked == "unlinked":
            total_statement = total_statement.where(Player.discord_id == None)
        total = (await session.exec(total_statement)).one()
        
        offset = (page - 1) * limit
        statement = statement.order_by(col(Player.steam_id)).offset(offset).limit(limit)
        db_players = (await session.exec(statement)).all()
        
        paginated_results: List[Dict[str, Any]] = []
        for p in db_players:
            paginated_results.append({
                "steam_id": p.steam_id,
                "discord_id": p.discord_id,
                "is_online": False,
                "is_linked": p.discord_id is not None,
                "name": "Sin Nickname"
            })
            
        steam_ids = [p["steam_id"] for p in paginated_results]
        if steam_ids:
            summaries = await get_player_summaries(steam_ids)
            for p in paginated_results:
                summary = summaries.get(p["steam_id"])
                if summary and "personaname" in summary:
                    p["name"] = summary["personaname"]
                    
            stmt = select(Membership).where(col(Membership.steam_id).in_(steam_ids), Membership.is_active == True)
            memberships = (await session.exec(stmt)).all()
            mem_map: Dict[str, List[str]] = {}
            for m in memberships:
                mem_map.setdefault(m.steam_id, []).append(m.membership_type)
            for p in paginated_results:
                p["active_memberships"] = mem_map.get(p["steam_id"], [])
        else:
            for p in paginated_results:
                p["active_memberships"] = []
            
        return {
            "total": total,
            "page": page,
            "limit": limit,
            "players": paginated_results
        }

    @staticmethod
    async def get_steam_players_batch(steam_ids: str) -> Dict[str, Any]:
        ids_list = [sid.strip() for sid in steam_ids.split(",") if sid.strip()]
        if not ids_list:
            return {}
        return await get_player_summaries(ids_list)
