from typing import Any, Dict, List, Optional
from fastapi import HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.connections.databases.db import Player, Role, PlayerRole
from src.modules.v1.schemas.dtos import RoleRegisterRequest

class RolesService:
    @staticmethod
    async def register_role(req: RoleRegisterRequest, session: AsyncSession) -> Dict[str, Any]:
        normalized_code = req.code.strip().upper()
        existing = (await session.exec(select(Role).where(Role.code == normalized_code))).first()
        if existing:
            # If already exists, update name, role_type and discord_role_id
            existing.name = req.name.strip()
            existing.role_type = req.role_type.strip().upper()
            existing.discord_role_id = req.discord_role_id.strip() if req.discord_role_id else None
            session.add(existing)
            await session.commit()
            return {"ok": True, "message": f"Role '{normalized_code}' updated successfully"}
        
        # Free-form dynamic role type: allows standard (SYSTEM, VIP, SPECIAL, PUBLIC) or custom (e.g. MASTERCHEF)
        normalized_type = req.role_type.strip().upper()
        role = Role(
            code=normalized_code,
            name=req.name.strip(),
            role_type=normalized_type,
            discord_role_id=req.discord_role_id.strip() if req.discord_role_id else None
        )
        session.add(role)
        await session.commit()
        return {"ok": True, "message": f"Role '{normalized_code}' registered successfully as type '{normalized_type}'"}

    @staticmethod
    async def get_all_roles(session: AsyncSession) -> List[Dict[str, Any]]:
        roles = (await session.exec(select(Role))).all()
        return [
            {
                "code": r.code,
                "name": r.name,
                "role_type": r.role_type,
                "discord_role_id": r.discord_role_id
            }
            for r in roles
        ]

    @staticmethod
    async def add_special_role(steam_id: str, role_id: str, session: AsyncSession) -> Dict[str, Any]:
        player = await session.get(Player, steam_id)
        if not player:
            raise HTTPException(status_code=404, detail="Player not found")
            
        role = (await session.exec(select(Role).where((Role.code == role_id) | (Role.discord_role_id == role_id)))).first()
        if not role:
            raise HTTPException(status_code=404, detail=f"Role code or discord_role_id '{role_id}' not registered")
            
        player_role = (await session.exec(select(PlayerRole).where(PlayerRole.steam_id == steam_id, PlayerRole.role_id == role.id))).first()
        if player_role:
            return {"ok": True, "message": "Player already has this role"}
            
        assert role.id is not None
        player_role = PlayerRole(steam_id=steam_id, role_id=role.id)
        session.add(player_role)
        await session.commit()
        return {"ok": True, "message": f"Role '{role.code}' added to player"}

    @staticmethod
    async def remove_special_role(steam_id: str, role_id: str, session: AsyncSession) -> Dict[str, Any]:
        role = (await session.exec(select(Role).where((Role.code == role_id) | (Role.discord_role_id == role_id)))).first()
        if not role:
            raise HTTPException(status_code=404, detail="Role not found")
            
        player_role = (await session.exec(select(PlayerRole).where(PlayerRole.steam_id == steam_id, PlayerRole.role_id == role.id))).first()
        if not player_role:
            raise HTTPException(status_code=404, detail="Player does not have this role")
            
        await session.delete(player_role)
        await session.commit()
        return {"ok": True, "message": f"Role '{role.code}' removed from player"}
