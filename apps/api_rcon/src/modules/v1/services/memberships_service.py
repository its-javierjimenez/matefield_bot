import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from fastapi import HTTPException
from sqlmodel import select, func, col, or_
from sqlmodel.ext.asyncio.session import AsyncSession

from src.connections.databases.db import Player, Membership, Role, PlayerRole, BotConfig, MembershipTypeConfig, MembershipType
from src.connections.apis.rcon import RCONManager
from src.modules.v1.schemas.dtos import AddMembershipRequest, EditMembershipRequest, CompensateRequest

logger = logging.getLogger("wardogs.memberships")

class MembershipsService:
    @staticmethod
    async def add_membership(req: AddMembershipRequest, session: AsyncSession) -> Dict[str, Any]:
        player = await session.get(Player, req.steam_id)
        if not player:
            raise HTTPException(status_code=404, detail="Player not found")
        
        norm_type = req.membership_type.strip().upper()
        m_type = (await session.exec(select(MembershipType).where(func.upper(MembershipType.code) == norm_type))).first()

        if req.days is None:
            if m_type is not None:
                days_to_add = m_type.default_days
            else:
                config_key = f"ROLE_DAYS_{norm_type}"
                config_days = (await session.exec(select(BotConfig).where(BotConfig.config_key == config_key))).first()
                days_to_add = int(config_days.config_value) if config_days else 30
        else:
            days_to_add = req.days

        # Check quota if it's a new membership or one that's inactive
        max_quota = m_type.max_quota if m_type else None
        if max_quota is None:
            legacy_config = (await session.exec(select(MembershipTypeConfig).where(MembershipTypeConfig.membership_type == norm_type))).first()
            if legacy_config:
                max_quota = legacy_config.max_quota

        if max_quota is not None:
            usage_stmt = select(func.count(col(Membership.id))).where(func.upper(Membership.membership_type) == norm_type, Membership.is_active == True)
            current_usage = (await session.exec(usage_stmt)).one()
            
            # If player already has this membership active, it doesn't count as a new slot
            existing_active = (await session.exec(
                select(Membership).where(
                    Membership.steam_id == req.steam_id,
                    func.upper(Membership.membership_type) == norm_type,
                    Membership.is_active == True
                )
            )).first()
            
            if not existing_active and current_usage >= max_quota:
                raise HTTPException(status_code=400, detail=f"No hay cupos disponibles para la membresía tipo {norm_type}. Límite de {max_quota} alcanzado.")

        # Determine server_id scope
        server_id = req.server_id if req.server_id is not None else (m_type.server_id if m_type else None)

        start_date = datetime.now(timezone.utc)
        end_date = start_date + timedelta(days=days_to_add) if days_to_add > 0 else None

        # Check for existing active membership
        existing_membership = (await session.exec(
            select(Membership).where(
                Membership.steam_id == req.steam_id,
                func.upper(Membership.membership_type) == norm_type,
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
            await MembershipsService._deactivate_membership(existing_membership, session)
            existing_membership.end_time = start_date # Mark it as ended now
            session.add(existing_membership)
        
        membership = Membership(
            steam_id=req.steam_id,
            membership_type=req.membership_type,
            start_time=start_date,
            end_time=end_date,
            is_active=True,
            is_booster=req.is_booster or False,
            server_id=server_id,
            tebex_transaction_id=req.tebex_transaction_id,
            tebex_subscription_id=req.tebex_subscription_id,
            payment_source=req.payment_source or "MANUAL"
        )
        
        # Link special role if passed or configured in MembershipType
        role_identifier = req.special_role or (m_type.discord_role_id if m_type and m_type.discord_role_id else None)
        if role_identifier:
            role = (await session.exec(select(Role).where(
                or_(Role.name == role_identifier, Role.discord_role_id == role_identifier, Role.code == role_identifier)
            ))).first()
            if not role:
                role = Role(code=role_identifier.upper().replace(" ", "_"), name=role_identifier, discord_role_id=role_identifier, role_type="SPECIAL")
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

    @staticmethod
    async def _deactivate_membership(m: Membership, session: AsyncSession, revoke_special_role: bool = False) -> None:
        """
        Desactiva una membresía (is_active = False).
        Por regla de negocio, los roles especiales (ej. VIP Fundador, insignias) son permanentes
        en la cuenta del jugador y perduran para siempre aunque la membresía expire.
        Solo se revocan de PlayerRole si revoke_special_role=True (exclusivamente ante reembolsos o disputas en Tebex).
        """
        m.is_active = False
        session.add(m)
        if revoke_special_role and m.special_role_id:
            other_active = (await session.exec(select(Membership).where(
                Membership.steam_id == m.steam_id,
                Membership.special_role_id == m.special_role_id,
                Membership.is_active == True,
                Membership.id != m.id
            ))).first()
            if not other_active:
                pr = (await session.exec(select(PlayerRole).where(
                    PlayerRole.steam_id == m.steam_id,
                    PlayerRole.role_id == m.special_role_id
                ))).first()
                if pr:
                    await session.delete(pr)

    @staticmethod
    async def edit_membership(membership_id: int, req: EditMembershipRequest, session: AsyncSession) -> Dict[str, Any]:
        membership = await session.get(Membership, membership_id)
        if not membership:
            raise HTTPException(status_code=404, detail="Membership not found")
            
        if req.membership_type is not None:
            norm_type = req.membership_type.strip().upper()
            membership.membership_type = req.membership_type
            
            # Si se edita el tipo y no se pasaron días explícitos, ajustar la fecha de acuerdo al tipo (achicarse o agrandarse)
            if req.days is None:
                m_type = (await session.exec(select(MembershipType).where(func.upper(MembershipType.code) == norm_type))).first()
                if m_type is not None:
                    type_days = m_type.default_days
                else:
                    if norm_type == "VIP_PERMANENTE":
                        type_days = 0
                    else:
                        config_key = f"ROLE_DAYS_{norm_type}"
                        config_days = (await session.exec(select(BotConfig).where(BotConfig.config_key == config_key))).first()
                        if config_days and config_days.config_value.isdigit():
                            type_days = int(config_days.config_value)
                        elif norm_type == "VIP_EXPRESS":
                            type_days = 15
                        else:
                            type_days = 30
                
                start_base = membership.start_time or datetime.now(timezone.utc)
                if start_base.tzinfo is None:
                    start_base = start_base.replace(tzinfo=timezone.utc)
                
                if type_days == 0 or norm_type == "VIP_PERMANENTE":
                    membership.end_time = None
                    if req.is_active is None:
                        membership.is_active = True
                else:
                    membership.end_time = start_base + timedelta(days=type_days)
                    if req.is_active is None:
                        now_utc = datetime.now(timezone.utc)
                        end_comp = membership.end_time if membership.end_time.tzinfo else membership.end_time.replace(tzinfo=timezone.utc)
                        membership.is_active = end_comp > now_utc
            
        if req.days is not None:
            if req.days == 0:
                membership.end_time = None
            else:
                membership.end_time = membership.start_time + timedelta(days=req.days)
                
        if req.add_days is not None:
            if membership.end_time is not None:
                membership.end_time = membership.end_time + timedelta(days=req.add_days)
                
        if req.is_active is not None:
            if not req.is_active:
                await MembershipsService._deactivate_membership(membership, session)
            else:
                membership.is_active = True
                session.add(membership)

        if req.is_booster is not None:
            membership.is_booster = req.is_booster

        if "server_id" in req.model_fields_set:
            membership.server_id = req.server_id
                        
        session.add(membership)
        await session.commit()
        return {"ok": True, "message": "Membership updated"}

    @staticmethod
    async def compensate_memberships(days: int, session: AsyncSession) -> Dict[str, Any]:
        stmt = select(Membership).where(Membership.is_active == True, Membership.end_time != None)
        active_memberships = (await session.exec(stmt)).all()
        
        count = 0
        for m in active_memberships:
            if m.end_time:
                m.end_time = m.end_time + timedelta(days=days)
                session.add(m)
                count += 1
            
        await session.commit()
        return {"ok": True, "message": f"Compensated {count} memberships with {days} days."}

    @staticmethod
    async def delete_membership(membership_id: int, session: AsyncSession) -> Dict[str, Any]:
        membership = await session.get(Membership, membership_id)
        if not membership:
            raise HTTPException(status_code=404, detail="Membership not found")
            
        was_active = membership.is_active
        await session.delete(membership)
        await session.commit()
        if was_active:
            try:
                await MembershipsService.sync_memberships_logic(session)
            except Exception as e:
                logger.warning(f"RCON sync notice after deleting membership #{membership_id}: {e}")
        return {"ok": True, "message": "Membership deleted"}

    @staticmethod
    async def get_paginated_memberships(page: int, limit: int, session: AsyncSession, discord_id: Optional[str] = None) -> Dict[str, Any]:
        target_steam_id = None
        if discord_id:
            player = (await session.exec(select(Player).where(Player.discord_id == discord_id))).first()
            if not player:
                return {
                    "page": page,
                    "limit": limit,
                    "total": 0,
                    "memberships": []
                }
            target_steam_id = player.steam_id

        offset = (page - 1) * limit
        statement = select(Membership).order_by(col(Membership.start_time).desc())
        total_statement = select(func.count(col(Membership.id)))
        if target_steam_id:
            statement = statement.where(Membership.steam_id == target_steam_id)
            total_statement = total_statement.where(Membership.steam_id == target_steam_id)

        statement = statement.offset(offset).limit(limit)
        memberships = (await session.exec(statement)).all()
        total = (await session.exec(total_statement)).one()
        
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
                "is_booster": m.is_booster,
                "server_id": m.server_id,
                "start_date": m.start_time.isoformat(),
                "end_date": m.end_time.isoformat() if m.end_time else None,
                "special_role": special_role_name,
                "special_role_id": m.special_role_id,
                "rcon_sync_status": "SUCCESS" if m.is_active else "INACTIVE",
            })
        
        return {
            "page": page,
            "limit": limit,
            "total": total,
            "memberships": results
        }

    @staticmethod
    async def sync_memberships_logic(session: AsyncSession) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        
        # 1. Expire old memberships
        expired_stmt = select(Membership).where(
            Membership.is_active == True,
            Membership.end_time != None,
            col(Membership.end_time) < now
        )
        expired = (await session.exec(expired_stmt)).all()
        for m in expired:
            await MembershipsService._deactivate_membership(m, session)
                        
        if expired:
            await session.commit()
            
        # 2. Get active steam_ids
        active_stmt = select(Membership.steam_id).where(Membership.is_active == True).distinct()
        active_steam_ids = set((await session.exec(active_stmt)).all())
        
        # 3. Sync RCON per-server (respecting server_id scope)
        try:
            active_servers = await RCONManager.get_all_active_servers(session)
            for s_info, client in active_servers:
                try:
                    if s_info.id is not None:
                        s_vip_stmt = select(Membership.steam_id).where(
                            Membership.is_active == True,
                            or_(Membership.server_id == None, Membership.server_id == s_info.id)
                        ).distinct()
                    else:
                        s_vip_stmt = select(Membership.steam_id).where(
                            Membership.is_active == True,
                            Membership.server_id == None
                        ).distinct()
                    server_steam_ids = list(set((await session.exec(s_vip_stmt)).all()))
                    await client.sync_reserved_slots(server_steam_ids)
                except Exception as s_err:
                    logger.warning(f"Failed to sync RCON reserved slots to {s_info.name} ({s_info.base_url}): {s_err}")
            
            for sid in active_steam_ids:
                m_stmt = select(Membership).where(Membership.steam_id == sid, Membership.is_active == True)
                for m in (await session.exec(m_stmt)).all():
                    if m.rcon_sync_status != "SUCCESS":
                        m.rcon_sync_status = "SUCCESS"
                        session.add(m)
            await session.commit()
            
        except Exception as e:
            logger.error(f"Failed to sync RCON reserved slots: {e}", exc_info=True)
            
        # 4. Prepare data for Discord Bot Role Sync
        players_stmt = select(Player).where(Player.discord_id != None)
        players = (await session.exec(players_stmt)).all()
        
        # Batch query all active memberships by steam_id to avoid N+1 queries
        active_m_stmt = select(Membership.steam_id, Membership.membership_type).where(Membership.is_active == True)
        all_active_m = (await session.exec(active_m_stmt)).all()
        m_types_by_steam: Dict[str, List[str]] = {}
        for sid, mtype in all_active_m:
            m_types_by_steam.setdefault(sid, []).append(mtype)

        # Batch query all special roles by steam_id to avoid N+1 queries
        pr_stmt = (
            select(PlayerRole.steam_id, Role.discord_role_id)
            .join(Role, PlayerRole.role_id == Role.id)
            .where(Role.discord_role_id != None)
        )
        all_pr = (await session.exec(pr_stmt)).all()
        roles_by_steam: Dict[str, List[int]] = {}
        for sid, dr_id in all_pr:
            if dr_id and str(dr_id).isdigit():
                roles_by_steam.setdefault(sid, []).append(int(dr_id))

        discord_sync_data = []
        for p in players:
            discord_sync_data.append({
                "discord_id": p.discord_id,
                "active_memberships": m_types_by_steam.get(p.steam_id, []),
                "special_roles": roles_by_steam.get(p.steam_id, [])
            })
            
        all_roles = (await session.exec(select(Role))).all()
        role_maps = {r.code: int(r.discord_role_id) for r in all_roles if r.discord_role_id and str(r.discord_role_id).isdigit()}
        
        # Also include discord_role_id from MembershipType if configured
        all_types = (await session.exec(select(MembershipType))).all()
        for mt in all_types:
            if mt.discord_role_id and str(mt.discord_role_id).isdigit():
                role_maps[mt.code] = int(mt.discord_role_id)

        managed_special_roles = [
            int(r.discord_role_id)
            for r in all_roles
            if r.role_type == "SPECIAL" and r.discord_role_id and str(r.discord_role_id).isdigit()
        ]
            
        return {
            "sync_data": discord_sync_data, 
            "role_maps": role_maps,
            "managed_special_roles": managed_special_roles
        }

    @staticmethod
    async def get_rcon_sync_status(session: AsyncSession) -> Dict[str, Any]:
        active_stmt = select(Membership.steam_id).where(Membership.is_active == True).distinct()
        active_steam_ids = set((await session.exec(active_stmt)).all())
        
        server_info, client = await RCONManager.get_default_server(session)
        try:
            current_slots_resp = await client.get_reserved_slots()
            current_slots = set(current_slots_resp.reservedSlots or [])
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch from RCON ({server_info.name}): {e}")
        
        synced = list(active_steam_ids.intersection(current_slots))
        pending_add = list(active_steam_ids - current_slots)
        pending_remove = list(current_slots - active_steam_ids)
        
        return {
            "server": server_info.name,
            "synced": synced,
            "pending_add": pending_add,
            "pending_remove": pending_remove
        }
