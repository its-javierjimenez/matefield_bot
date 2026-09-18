from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends
from wardogs_schemas import v1 as schemas

from src.security.guard import verify_api_key_guard
from src.connections.apis.rcon import rcon_client as rcon
from src.modules.v1.schemas.dtos import ConfigUpdateRequest
from src.modules.v1.services.server_service import ServerService

router = APIRouter(tags=["Server & RCON"])

@router.get("/status", dependencies=[Depends(verify_api_key_guard)], response_model=schemas.Status)
async def get_status():
    return await ServerService.get_status()

@router.get("/players", dependencies=[Depends(verify_api_key_guard)], response_model=schemas.Players1)
async def get_players():
    return await ServerService.get_players()

@router.get("/audit", dependencies=[Depends(verify_api_key_guard)], response_model=schemas.Audit)
async def get_audit(limit: int = 50):
    return await ServerService.get_audit_logs(limit)

@router.get("/reserved-slots", dependencies=[Depends(verify_api_key_guard)], response_model=schemas.ReservedSlots)
async def get_reserved_slots():
    return await ServerService.get_reserved_slots()

@router.post("/reserved-slots", dependencies=[Depends(verify_api_key_guard)], response_model=schemas.Ok)
async def add_reserved_slot(req: schemas.Player):
    await ServerService.add_reserved_slot(req.steam_id)
    return {"ok": True}

@router.delete("/reserved-slots/{steam_id}", dependencies=[Depends(verify_api_key_guard)], response_model=schemas.Ok)
async def remove_reserved_slot(steam_id: str):
    await ServerService.remove_reserved_slot(steam_id)
    return {"ok": True}

@router.post("/broadcast", dependencies=[Depends(verify_api_key_guard)], response_model=schemas.Ok)
async def broadcast(req: schemas.MessageRequest):
    await ServerService.broadcast(req.message)
    return {"ok": True}

@router.post("/players/{steam_id}/message", dependencies=[Depends(verify_api_key_guard)], response_model=schemas.Ok)
async def send_player_message(steam_id: str, req: schemas.MessageRequest):
    await ServerService.send_player_message(steam_id, req.message)
    return {"ok": True}

@router.post("/players/{steam_id}/kick", dependencies=[Depends(verify_api_key_guard)], response_model=schemas.Ok)
async def kick_player(steam_id: str, req: schemas.ReasonRequest):
    await ServerService.kick_player(steam_id, req.reason or "")
    return {"ok": True}

@router.post("/players/{steam_id}/faction", dependencies=[Depends(verify_api_key_guard)], response_model=schemas.Ok)
async def switch_faction(steam_id: str, req: schemas.FactionRequest):
    await ServerService.switch_faction(steam_id, req.faction)
    return {"ok": True}

@router.get("/config", dependencies=[Depends(verify_api_key_guard)])
async def get_config():
    return await rcon.get_config()

@router.put("/config", dependencies=[Depends(verify_api_key_guard)], response_model=schemas.ConfigResult)
async def update_config(req: ConfigUpdateRequest):
    return await ServerService.update_config(req.revision, req.new_text)
