from typing import Any, Dict, List, Optional
from src.connections.apis.rcon import rcon_client as rcon
from wardogs_schemas import v1 as schemas

class ServerService:
    @staticmethod
    async def get_status() -> schemas.Status:
        return await rcon.get_status()

    @staticmethod
    async def get_players() -> schemas.Players1:
        return await rcon.get_players()

    @staticmethod
    async def get_audit_logs(limit: int = 50) -> schemas.Audit:
        return await rcon.get_audit_logs(limit)

    @staticmethod
    async def broadcast(message: str) -> None:
        await rcon.broadcast(message)

    @staticmethod
    async def send_player_message(steam_id: str, message: str) -> None:
        await rcon.send_player_message(steam_id, message)

    @staticmethod
    async def kick_player(steam_id: str, reason: str) -> None:
        await rcon.kick_player(steam_id, reason)

    @staticmethod
    async def ban_player(steam_id: str, reason: str) -> None:
        await rcon.ban_player(steam_id, reason)

    @staticmethod
    async def switch_faction(steam_id: str, faction: str) -> None:
        await rcon.switch_faction(steam_id, faction)

    @staticmethod
    async def get_reserved_slots() -> schemas.ReservedSlots:
        return await rcon.get_reserved_slots()

    @staticmethod
    async def add_reserved_slot(steam_id: str) -> None:
        current = await rcon.get_reserved_slots()
        slots = set(current.reservedSlots or [])
        slots.add(steam_id)
        await rcon.sync_reserved_slots(list(slots))

    @staticmethod
    async def remove_reserved_slot(steam_id: str) -> None:
        current = await rcon.get_reserved_slots()
        slots = set(current.reservedSlots or [])
        slots.discard(steam_id)
        await rcon.sync_reserved_slots(list(slots))

    @staticmethod
    async def update_config(revision: str, new_text: str) -> schemas.ConfigResult:
        return await rcon.update_config(revision, new_text)
