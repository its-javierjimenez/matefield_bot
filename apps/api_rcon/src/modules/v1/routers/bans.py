from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession
from wardogs_schemas import v1 as schemas

from src.security.guard import verify_api_key_guard
from src.connections.databases.db import get_session
from src.modules.v1.services.bans_service import BansService

router = APIRouter(tags=["Bans"])

@router.post("/db/sync_bans", dependencies=[Depends(verify_api_key_guard)])
async def sync_bans(session: AsyncSession = Depends(get_session)):
    return await BansService.sync_bans(session)

@router.post("/players/{steam_id}/ban", dependencies=[Depends(verify_api_key_guard)], response_model=schemas.Ok)
async def ban_player(steam_id: str, req: schemas.ReasonRequest, session: AsyncSession = Depends(get_session)):
    return await BansService.ban_player(steam_id, req, session)

@router.post("/players/{steam_id}/unban", dependencies=[Depends(verify_api_key_guard)], response_model=schemas.Ok)
async def unban_player(steam_id: str, session: AsyncSession = Depends(get_session)):
    return await BansService.unban_player(steam_id, session)

@router.get("/db/bans", dependencies=[Depends(verify_api_key_guard)], response_model=schemas.DbBansResponse)
async def get_db_bans(steam_id: Optional[str] = None, session: AsyncSession = Depends(get_session)):
    return await BansService.get_bans(steam_id, session)
