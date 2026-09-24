from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from src.security.guard import verify_api_key_guard
from src.connections.databases.db import get_session
from src.modules.v1.schemas.dtos import CreateRconServerRequest, UpdateRconServerRequest
from src.modules.v1.services.rcon_servers_service import RconServersService
from src.modules.v1.services.memberships_service import MembershipsService
from src.modules.v1.services.bans_service import BansService

router = APIRouter(prefix="/rcon-servers", tags=["Multi-RCON Servers"])


@router.get("", dependencies=[Depends(verify_api_key_guard)])
async def list_rcon_servers(
    check_health: bool = True,
    session: AsyncSession = Depends(get_session)
) -> List[Dict[str, Any]]:
    return await RconServersService.list_servers(session, check_health=check_health)


@router.post("", dependencies=[Depends(verify_api_key_guard)])
async def create_rcon_server(
    req: CreateRconServerRequest,
    session: AsyncSession = Depends(get_session)
) -> Dict[str, Any]:
    return await RconServersService.create_server(req, session)


@router.get("/{server_id}", dependencies=[Depends(verify_api_key_guard)])
async def get_rcon_server(
    server_id: int,
    session: AsyncSession = Depends(get_session)
) -> Dict[str, Any]:
    return await RconServersService.get_server(server_id, session)


@router.put("/{server_id}", dependencies=[Depends(verify_api_key_guard)])
async def update_rcon_server(
    server_id: int,
    req: UpdateRconServerRequest,
    session: AsyncSession = Depends(get_session)
) -> Dict[str, Any]:
    return await RconServersService.update_server(server_id, req, session)


@router.delete("/{server_id}", dependencies=[Depends(verify_api_key_guard)])
async def delete_rcon_server(
    server_id: int,
    session: AsyncSession = Depends(get_session)
) -> Dict[str, Any]:
    return await RconServersService.delete_server(server_id, session)


@router.post("/{server_id}/test", dependencies=[Depends(verify_api_key_guard)])
async def test_rcon_server(
    server_id: int,
    session: AsyncSession = Depends(get_session)
) -> Dict[str, Any]:
    return await RconServersService.test_server(server_id, session)


@router.post("/sync-all", dependencies=[Depends(verify_api_key_guard)])
async def sync_all_rcon_servers(
    session: AsyncSession = Depends(get_session)
) -> Dict[str, Any]:
    return await RconServersService.sync_all_servers(session)
