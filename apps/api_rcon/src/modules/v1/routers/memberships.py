from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession
from wardogs_schemas import v1 as schemas

from src.security.guard import verify_api_key_guard
from src.connections.databases.db import get_session
from src.modules.v1.schemas.dtos import (
    AddMembershipRequest, EditMembershipRequest, CompensateRequest
)
from src.modules.v1.services.memberships_service import MembershipsService

router = APIRouter(tags=["Memberships"])

@router.post("/db/players/membership", dependencies=[Depends(verify_api_key_guard)], response_model=schemas.Ok)
async def add_membership(req: AddMembershipRequest, session: AsyncSession = Depends(get_session)):
    return await MembershipsService.add_membership(req, session)

@router.put("/db/memberships/{membership_id}", dependencies=[Depends(verify_api_key_guard)], response_model=schemas.Ok)
async def edit_membership(membership_id: int, req: EditMembershipRequest, session: AsyncSession = Depends(get_session)):
    return await MembershipsService.edit_membership(membership_id, req, session)

@router.post("/db/memberships/compensate", dependencies=[Depends(verify_api_key_guard)], response_model=schemas.Ok)
async def compensate_memberships(req: CompensateRequest, session: AsyncSession = Depends(get_session)):
    return await MembershipsService.compensate_memberships(req.days, session)

@router.delete("/db/memberships/{membership_id}", dependencies=[Depends(verify_api_key_guard)], response_model=schemas.Ok)
async def delete_membership(membership_id: int, session: AsyncSession = Depends(get_session)):
    return await MembershipsService.delete_membership(membership_id, session)

@router.get("/db/memberships", dependencies=[Depends(verify_api_key_guard)])
async def get_paginated_memberships(page: int = 1, limit: int = 10, session: AsyncSession = Depends(get_session)):
    return await MembershipsService.get_paginated_memberships(page, limit, session)

@router.post("/db/sync_memberships", dependencies=[Depends(verify_api_key_guard)])
async def sync_memberships_endpoint(session: AsyncSession = Depends(get_session)):
    return await MembershipsService.sync_memberships_logic(session)

@router.get("/db/rcon_sync_status", dependencies=[Depends(verify_api_key_guard)])
async def rcon_sync_status(session: AsyncSession = Depends(get_session)):
    return await MembershipsService.get_rcon_sync_status(session)
