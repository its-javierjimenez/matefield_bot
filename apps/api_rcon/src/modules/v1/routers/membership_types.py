from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession

from src.security.guard import verify_api_key_guard
from src.connections.databases.db import get_session
from src.modules.v1.schemas.dtos import (
    CreateMembershipTypeRequest,
    UpdateMembershipTypeRequest,
)
from src.modules.v1.services.membership_types_service import MembershipTypesService

router = APIRouter(prefix="/membership-types", tags=["Membership Types"])


@router.get("", dependencies=[Depends(verify_api_key_guard)])
async def list_membership_types(
    active_only: bool = False,
    session: AsyncSession = Depends(get_session)
) -> List[Dict[str, Any]]:
    return await MembershipTypesService.list_types(session, active_only=active_only)


@router.post("", dependencies=[Depends(verify_api_key_guard)])
async def create_membership_type(
    req: CreateMembershipTypeRequest,
    session: AsyncSession = Depends(get_session)
) -> Dict[str, Any]:
    return await MembershipTypesService.create_type(req, session)


@router.get("/{identifier}", dependencies=[Depends(verify_api_key_guard)])
async def get_membership_type(
    identifier: str,
    session: AsyncSession = Depends(get_session)
) -> Dict[str, Any]:
    m_type = await MembershipTypesService.get_type(identifier, session)
    if not m_type:
        raise HTTPException(status_code=404, detail="Tipo de membresía no encontrado")
    return {
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


@router.put("/{type_id}", dependencies=[Depends(verify_api_key_guard)])
async def update_membership_type(
    type_id: int,
    req: UpdateMembershipTypeRequest,
    session: AsyncSession = Depends(get_session)
) -> Dict[str, Any]:
    return await MembershipTypesService.update_type(type_id, req, session)


@router.delete("/{type_id}", dependencies=[Depends(verify_api_key_guard)])
async def delete_membership_type(
    type_id: int,
    session: AsyncSession = Depends(get_session)
) -> Dict[str, Any]:
    return await MembershipTypesService.delete_type(type_id, session)
