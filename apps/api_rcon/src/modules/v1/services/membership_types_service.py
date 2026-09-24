from __future__ import annotations
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timezone
from sqlmodel import select, func, col
from sqlmodel.ext.asyncio.session import AsyncSession
from fastapi import HTTPException

from src.connections.databases.db import MembershipType, Membership, RconServer, MembershipTypeConfig
from src.modules.v1.schemas.dtos import (
    CreateMembershipTypeRequest,
    UpdateMembershipTypeRequest,
    MembershipTypeItem,
)


class MembershipTypesService:

    @staticmethod
    async def list_types(session: AsyncSession, active_only: bool = False) -> List[Dict[str, Any]]:
        # Ensure default types exist if table is fresh
        await MembershipTypesService._ensure_defaults(session)

        stmt = select(MembershipType)
        if active_only:
            stmt = stmt.where(MembershipType.is_active == True)
        stmt = stmt.order_by(col(MembershipType.id))

        types = (await session.exec(stmt)).all()

        # Calculate current usage per membership type
        usage_stmt = (
            select(Membership.membership_type, func.count(col(Membership.id)))
            .where(Membership.is_active == True)
            .group_by(Membership.membership_type)
        )
        usage_rows = (await session.exec(usage_stmt)).all()
        usage_map = {m_type.upper(): count for m_type, count in usage_rows}

        # Resolve server names
        server_ids = [t.server_id for t in types if t.server_id is not None]
        server_names: Dict[int, str] = {}
        if server_ids:
            servers_stmt = select(RconServer).where(col(RconServer.id).in_(server_ids))
            servers = (await session.exec(servers_stmt)).all()
            server_names = {s.id: s.name for s in servers if s.id is not None}

        result = []
        for t in types:
            code_upper = t.code.upper()
            result.append({
                "id": t.id,
                "code": t.code,
                "name": t.name,
                "description": t.description,
                "price_usd": t.price_usd,
                "billing_type": t.billing_type,
                "default_days": t.default_days,
                "max_quota": t.max_quota,
                "current_usage": usage_map.get(code_upper, 0),
                "discord_role_id": t.discord_role_id,
                "server_id": t.server_id,
                "server_name": server_names.get(t.server_id) if t.server_id else "Global (Todos)",
                "tebex_package_id": t.tebex_package_id,
                "is_active": t.is_active,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "updated_at": t.updated_at.isoformat() if t.updated_at else None,
            })
        return result

    @staticmethod
    async def get_type(identifier: Union[int, str], session: AsyncSession) -> Optional[MembershipType]:
        if isinstance(identifier, int) or (isinstance(identifier, str) and identifier.isdigit()):
            return await session.get(MembershipType, int(identifier))
        code = str(identifier).strip().upper()
        stmt = select(MembershipType).where(func.upper(MembershipType.code) == code)
        return (await session.exec(stmt)).first()

    @staticmethod
    async def create_type(req: CreateMembershipTypeRequest, session: AsyncSession) -> Dict[str, Any]:
        normalized_code = req.code.strip().upper()

        existing = (await session.exec(
            select(MembershipType).where(func.upper(MembershipType.code) == normalized_code)
        )).first()
        if existing:
            raise HTTPException(status_code=400, detail=f"Ya existe un tipo de membresía con el código '{normalized_code}'")

        if req.server_id is not None:
            server = await session.get(RconServer, req.server_id)
            if not server:
                raise HTTPException(status_code=404, detail=f"Servidor RCON con ID {req.server_id} no encontrado")

        billing_type = req.billing_type.upper() if req.billing_type else "ONE_TIME"
        if billing_type not in ("ONE_TIME", "RECURRING"):
            raise HTTPException(status_code=400, detail="billing_type debe ser 'ONE_TIME' o 'RECURRING'")

        now = datetime.now(timezone.utc)
        m_type = MembershipType(
            code=normalized_code,
            name=req.name.strip(),
            description=req.description,
            price_usd=max(0.0, float(req.price_usd)),
            billing_type=billing_type,
            default_days=req.default_days if req.default_days is not None else 30,
            max_quota=req.max_quota,
            discord_role_id=str(req.discord_role_id).strip() if req.discord_role_id else None,
            server_id=req.server_id,
            tebex_package_id=req.tebex_package_id,
            is_active=req.is_active,
            created_at=now,
            updated_at=now,
        )
        session.add(m_type)
        await session.commit()
        await session.refresh(m_type)

        # Also keep membership_type_configs in sync for backwards compatibility
        config = (await session.exec(
            select(MembershipTypeConfig).where(MembershipTypeConfig.membership_type == normalized_code)
        )).first()
        if not config:
            session.add(MembershipTypeConfig(membership_type=normalized_code, max_quota=req.max_quota))
            await session.commit()

        return {
            "ok": True,
            "message": f"Tipo de membresía '{m_type.name}' creado exitosamente",
            "membership_type": {
                "id": m_type.id,
                "code": m_type.code,
                "name": m_type.name,
                "description": m_type.description,
                "price_usd": m_type.price_usd,
                "billing_type": m_type.billing_type,
                "default_days": m_type.default_days,
                "max_quota": m_type.max_quota,
                "current_usage": 0,
                "discord_role_id": m_type.discord_role_id,
                "server_id": m_type.server_id,
                "tebex_package_id": m_type.tebex_package_id,
                "is_active": m_type.is_active,
                "created_at": m_type.created_at.isoformat() if m_type.created_at else None,
                "updated_at": m_type.updated_at.isoformat() if m_type.updated_at else None,
            }
        }

    @staticmethod
    async def update_type(type_id: int, req: UpdateMembershipTypeRequest, session: AsyncSession) -> Dict[str, Any]:
        m_type = await session.get(MembershipType, type_id)
        if not m_type:
            raise HTTPException(status_code=404, detail="Tipo de membresía no encontrado")

        if req.server_id is not None:
            server = await session.get(RconServer, req.server_id)
            if not server:
                raise HTTPException(status_code=404, detail=f"Servidor RCON con ID {req.server_id} no encontrado")
            m_type.server_id = req.server_id
        elif req.server_id is None and "server_id" in req.model_fields_set:
            m_type.server_id = None

        if req.name is not None:
            m_type.name = req.name.strip()
        if req.description is not None:
            m_type.description = req.description
        if req.price_usd is not None:
            m_type.price_usd = max(0.0, float(req.price_usd))
        if req.billing_type is not None:
            b_type = req.billing_type.upper()
            if b_type not in ("ONE_TIME", "RECURRING"):
                raise HTTPException(status_code=400, detail="billing_type debe ser 'ONE_TIME' o 'RECURRING'")
            m_type.billing_type = b_type
        if req.default_days is not None:
            m_type.default_days = req.default_days
        if "max_quota" in req.model_fields_set:
            m_type.max_quota = req.max_quota
        if "discord_role_id" in req.model_fields_set:
            m_type.discord_role_id = str(req.discord_role_id).strip() if req.discord_role_id else None
        if "tebex_package_id" in req.model_fields_set:
            m_type.tebex_package_id = req.tebex_package_id
        if req.is_active is not None:
            m_type.is_active = req.is_active

        m_type.updated_at = datetime.now(timezone.utc)
        session.add(m_type)
        await session.commit()
        await session.refresh(m_type)

        # Sync quota to MembershipTypeConfig
        config = (await session.exec(
            select(MembershipTypeConfig).where(MembershipTypeConfig.membership_type == m_type.code.upper())
        )).first()
        if config:
            config.max_quota = m_type.max_quota
            session.add(config)
            await session.commit()

        return {
            "ok": True,
            "message": f"Tipo de membresía '{m_type.name}' actualizado exitosamente",
            "membership_type": {
                "id": m_type.id,
                "code": m_type.code,
                "name": m_type.name,
                "description": m_type.description,
                "price_usd": m_type.price_usd,
                "billing_type": m_type.billing_type,
                "default_days": m_type.default_days,
                "max_quota": m_type.max_quota,
                "discord_role_id": m_type.discord_role_id,
                "server_id": m_type.server_id,
                "tebex_package_id": m_type.tebex_package_id,
                "is_active": m_type.is_active,
                "created_at": m_type.created_at.isoformat() if m_type.created_at else None,
                "updated_at": m_type.updated_at.isoformat() if m_type.updated_at else None,
            }
        }

    @staticmethod
    async def delete_type(type_id: int, session: AsyncSession) -> Dict[str, Any]:
        m_type = await session.get(MembershipType, type_id)
        if not m_type:
            raise HTTPException(status_code=404, detail="Tipo de membresía no encontrado")

        # Soft delete
        m_type.is_active = False
        m_type.updated_at = datetime.now(timezone.utc)
        session.add(m_type)
        await session.commit()

        return {"ok": True, "message": f"Tipo de membresía '{m_type.name}' desactivado"}

    @staticmethod
    async def _ensure_defaults(session: AsyncSession) -> None:
        """Seeds initial default types if the membership_types table is empty, or links tebex IDs."""
        count = (await session.exec(select(func.count(col(MembershipType.id))))).one()
        if count == 0:
            existing_configs = (await session.exec(select(MembershipTypeConfig))).all()
            quota_map = {c.membership_type.upper(): c.max_quota for c in existing_configs}

            defaults = [
                ("VIP_COMUN", "VIP Común", "Membresía estándar mensual con slot reservado", 6.0, 30, 7682027),
                ("VIP_EXPRESS", "VIP Express", "Pase rápido quincenal con slot reservado", 4.0, 15, 7682061),
                ("VIP_PERMANENTE", "VIP Permanente", "Membresía vitalicia sin expiración", 0.0, 0, None),
            ]

            now = datetime.now(timezone.utc)
            for code, name, desc, price, days, tebex_id in defaults:
                quota = quota_map.get(code)
                session.add(MembershipType(
                    code=code,
                    name=name,
                    description=desc,
                    price_usd=price,
                    billing_type="ONE_TIME",
                    default_days=days,
                    max_quota=quota,
                    discord_role_id=None,
                    server_id=None,
                    tebex_package_id=tebex_id,
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                ))
            await session.commit()
        else:
            # Check and link tebex_package_id if missing on existing defaults
            all_types = (await session.exec(select(MembershipType))).all()
            updated = False
            for m in all_types:
                if m.code == "VIP_COMUN" and not m.tebex_package_id:
                    m.tebex_package_id = 7682027
                    m.price_usd = 6.0
                    session.add(m)
                    updated = True
                elif m.code == "VIP_EXPRESS" and not m.tebex_package_id:
                    m.tebex_package_id = 7682061
                    m.price_usd = 4.0
                    m.default_days = 15
                    session.add(m)
                    updated = True
            if updated:
                await session.commit()
