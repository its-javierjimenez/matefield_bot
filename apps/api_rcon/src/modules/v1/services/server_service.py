import logging
from typing import Any, Dict, List, Optional
from sqlmodel.ext.asyncio.session import AsyncSession
from wardogs_schemas import v1 as schemas

from src.connections.apis.rcon import rcon_client as rcon, RCONManager

logger = logging.getLogger("wardogs.server_service")


class ServerService:
    @staticmethod
    async def get_status(session: Optional[AsyncSession] = None) -> schemas.Status:
        if session:
            _, client = await RCONManager.get_default_server(session)
            return await client.get_status()
        return await rcon.get_status()

    @staticmethod
    async def get_players(session: Optional[AsyncSession] = None) -> schemas.Players1:
        if session:
            _, client = await RCONManager.get_default_server(session)
            return await client.get_players()
        return await rcon.get_players()

    @staticmethod
    async def get_audit_logs(limit: int = 50, session: Optional[AsyncSession] = None) -> schemas.Audit:
        if session:
            _, client = await RCONManager.get_default_server(session)
            return await client.get_audit_logs(limit)
        return await rcon.get_audit_logs(limit)

    @staticmethod
    async def broadcast(message: str, session: Optional[AsyncSession] = None) -> None:
        if session:
            active_servers = await RCONManager.get_all_active_servers(session)
            for s_info, client in active_servers:
                try:
                    await client.broadcast(message)
                except Exception as e:
                    logger.warning(f"Failed to broadcast to {s_info.name}: {e}")
        else:
            await rcon.broadcast(message)

    @staticmethod
    async def send_player_message(steam_id: str, message: str, session: Optional[AsyncSession] = None) -> None:
        if session:
            active_servers = await RCONManager.get_all_active_servers(session)
            for s_info, client in active_servers:
                try:
                    await client.send_player_message(steam_id, message)
                except Exception as e:
                    logger.debug(f"Failed to send player message on {s_info.name}: {e}")
        else:
            await rcon.send_player_message(steam_id, message)

    @staticmethod
    async def kick_player(steam_id: str, reason: str, session: Optional[AsyncSession] = None) -> None:
        if session:
            active_servers = await RCONManager.get_all_active_servers(session)
            for s_info, client in active_servers:
                try:
                    await client.kick_player(steam_id, reason)
                except Exception as e:
                    logger.debug(f"Failed to kick player on {s_info.name}: {e}")
        else:
            await rcon.kick_player(steam_id, reason)

    @staticmethod
    async def ban_player(steam_id: str, reason: str, session: Optional[AsyncSession] = None) -> None:
        if session:
            active_servers = await RCONManager.get_all_active_servers(session)
            for s_info, client in active_servers:
                try:
                    await client.ban_player(steam_id, reason)
                except Exception as e:
                    logger.debug(f"Failed to ban player on {s_info.name}: {e}")
        else:
            await rcon.ban_player(steam_id, reason)

    @staticmethod
    async def switch_faction(steam_id: str, faction: str, session: Optional[AsyncSession] = None) -> None:
        if session:
            _, client = await RCONManager.get_default_server(session)
            await client.switch_faction(steam_id, faction)
        else:
            await rcon.switch_faction(steam_id, faction)

    @staticmethod
    async def get_reserved_slots(session: Optional[AsyncSession] = None) -> schemas.ReservedSlots:
        if session:
            _, client = await RCONManager.get_default_server(session)
            return await client.get_reserved_slots()
        return await rcon.get_reserved_slots()

    @staticmethod
    async def add_reserved_slot(steam_id: str, session: Optional[AsyncSession] = None) -> None:
        if session:
            active_servers = await RCONManager.get_all_active_servers(session)
            for s_info, client in active_servers:
                try:
                    current = await client.get_reserved_slots()
                    slots = set(current.reservedSlots or [])
                    slots.add(steam_id)
                    await client.sync_reserved_slots(list(slots))
                except Exception as e:
                    logger.warning(f"Failed to add reserved slot on {s_info.name}: {e}")
        else:
            current = await rcon.get_reserved_slots()
            slots = set(current.reservedSlots or [])
            slots.add(steam_id)
            await rcon.sync_reserved_slots(list(slots))

    @staticmethod
    async def remove_reserved_slot(steam_id: str, session: Optional[AsyncSession] = None) -> None:
        if session:
            active_servers = await RCONManager.get_all_active_servers(session)
            for s_info, client in active_servers:
                try:
                    current = await client.get_reserved_slots()
                    slots = set(current.reservedSlots or [])
                    slots.discard(steam_id)
                    await client.sync_reserved_slots(list(slots))
                except Exception as e:
                    logger.warning(f"Failed to remove reserved slot on {s_info.name}: {e}")
        else:
            current = await rcon.get_reserved_slots()
            slots = set(current.reservedSlots or [])
            slots.discard(steam_id)
            await rcon.sync_reserved_slots(list(slots))

    @staticmethod
    async def update_config(revision: str, new_text: str, session: Optional[AsyncSession] = None) -> schemas.ConfigResult:
        if session:
            _, client = await RCONManager.get_default_server(session)
            return await client.update_config(revision, new_text)
        return await rcon.update_config(revision, new_text)
