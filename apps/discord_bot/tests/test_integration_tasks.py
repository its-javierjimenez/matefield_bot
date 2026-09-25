import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone, timedelta
from src.plugins.tasks import check_expired_bans, sync_ban_roles, membership_monitor, plugin
from wardogs_schemas import v1 as schemas

@pytest.mark.asyncio
async def test_check_expired_bans_multi_guild():
    # Setup mocks
    mock_api = AsyncMock()
    mock_app = MagicMock()
    mock_app.cache = MagicMock()
    mock_app.rest = AsyncMock()

    # Expired ban
    expired_time = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    mock_ban = schemas.DbBan(
        id=1,
        steam_id="76561198000000001",
        reason="Test expired ban",
        is_active=True,
        banned_at=datetime.now(timezone.utc).isoformat(),
        expires_at=expired_time
    )
    
    mock_bans_resp = MagicMock()
    mock_bans_resp.bans = [mock_ban]
    mock_api.get_db_bans.return_value = mock_bans_resp
    mock_api.get_bot_configs.return_value = {
        "BAN_ROLE_DEFAULT": "1001",
        "BAN_UNSET_ROLE_ID": "2001"
    }
    mock_api.get_player_by_steam.return_value = {
        "steam_id": "76561198000000001",
        "discord_id": "999888777"
    }

    # Two guilds: guild 10 has the ban role, guild 20 does not, guild 30 has the ban role
    mock_app.cache.get_guilds_view.return_value = {10: MagicMock(), 20: MagicMock(), 30: MagicMock()}
    mock_app.cache.get_roles_view_for_guild.side_effect = lambda g_id: {
        10: {1001: MagicMock()},
        20: {5555: MagicMock()}, # Doesn't have ban role
        30: {1001: MagicMock(), 2001: MagicMock()}
    }.get(g_id, {})

    # Members in guilds 10 and 30
    member_g10 = MagicMock()
    member_g10.role_ids = [1001]
    member_g10.remove_role = AsyncMock()
    member_g10.add_role = AsyncMock()

    member_g30 = MagicMock()
    member_g30.role_ids = [1001]
    member_g30.remove_role = AsyncMock()
    member_g30.add_role = AsyncMock()

    async def fetch_member(g_id, d_id):
        if g_id == 10:
            return member_g10
        if g_id == 30:
            return member_g30
        return None

    mock_app.rest.fetch_member.side_effect = fetch_member

    mock_client = MagicMock()
    mock_client.model = MagicMock()
    mock_client.model.api = mock_api
    mock_client.app = mock_app

    orig_client = getattr(plugin, "_client", None)
    try:
        plugin._client = mock_client

        await check_expired_bans.metadata.callback()

        # Check API unban called
        mock_api.unban_player.assert_called_once_with("76561198000000001")
        
        # Check roles stripped in guild 10 and 30
        member_g10.remove_role.assert_called_once_with(1001, reason="Ban Expirado")
        member_g30.remove_role.assert_called_once_with(1001, reason="Ban Expirado")

        # Check unset role added in guild 10 and 30
        member_g10.add_role.assert_called_once_with(2001, reason="Ban Expirado: rol restituido")
        member_g30.add_role.assert_called_once_with(2001, reason="Ban Expirado: rol restituido")
    finally:
        plugin._client = orig_client


@pytest.mark.asyncio
async def test_sync_ban_roles_assigns_and_revokes():
    mock_api = AsyncMock()
    mock_app = MagicMock()
    mock_app.cache = MagicMock()
    mock_app.rest = AsyncMock()

    mock_ban = schemas.DbBan(
        id=2,
        steam_id="76561198000000002",
        reason="Active ban",
        is_active=True,
        banned_at=datetime.now(timezone.utc).isoformat(),
        expires_at=None
    )
    mock_bans_resp = MagicMock()
    mock_bans_resp.bans = [mock_ban]
    mock_api.get_db_bans.return_value = mock_bans_resp
    mock_api.get_bot_configs.return_value = {
        "BAN_ROLE_DEFAULT": "1001",
        "BAN_UNSET_ROLE_ID": "2001"
    }
    mock_api.get_paginated_players.return_value = {
        "players": [{"steam_id": "76561198000000002", "discord_id": "999888777"}]
    }

    mock_app.cache.get_guilds_view.return_value = {10: MagicMock()}
    mock_app.cache.get_roles_view_for_guild.return_value = {1001: MagicMock(), 2001: MagicMock()}

    member = MagicMock()
    member.role_ids = [2001] # Currently has unban role, missing ban role
    member.add_role = AsyncMock()
    member.remove_role = AsyncMock()
    mock_app.rest.fetch_member.return_value = member

    mock_client = MagicMock()
    mock_client.model = MagicMock()
    mock_client.model.api = mock_api
    mock_client.app = mock_app

    orig_client = getattr(plugin, "_client", None)
    try:
        plugin._client = mock_client

        await sync_ban_roles.metadata.callback()

        mock_api.sync_bans.assert_called_once()
        member.add_role.assert_called_once_with(1001, reason="Ban sincronizado desde RCON/DB")
        member.remove_role.assert_called_once_with(2001, reason="Ban sincronizado: rol revocado")
    finally:
        plugin._client = orig_client


@pytest.mark.asyncio
async def test_membership_monitor_syncs_roles_and_respects_whitelist():
    mock_api = AsyncMock()
    mock_app = MagicMock()
    mock_app.cache = MagicMock()
    mock_app.rest = AsyncMock()

    mock_api.sync_memberships.return_value = {
        "sync_data": [
            {
                "discord_id": "111111",
                "active_memberships": ["VIP_COMUN"],
                "special_roles": []
            },
            {
                "discord_id": "222222", # Whitelisted
                "active_memberships": [],
                "special_roles": []
            }
        ],
        "role_maps": {"VIP_COMUN": 5001, "VIP_PRO": 5002},
        "managed_special_roles": []
    }

    mock_api.get_bot_configs.return_value = {
        "SYNC_WHITELIST": "222222",
        "LINK_ROLE_ID": "9999",
        "BAN_ROLE_DEFAULT": "8888"
    }

    mock_app.cache.get_guilds_view.return_value = {10: MagicMock()}
    mock_app.cache.get_roles_view_for_guild.return_value = {5001: MagicMock(), 5002: MagicMock()}

    # Member 111111 currently has expired VIP_PRO (5002), needs VIP_COMUN (5001)
    member_1 = MagicMock()
    member_1.role_ids = [5002, 9999] # 9999 is LINK_ROLE_ID
    mock_app.cache.get_member.return_value = member_1

    mock_client = MagicMock()
    mock_client.model = MagicMock()
    mock_client.model.api = mock_api
    mock_client.app = mock_app

    orig_client = getattr(plugin, "_client", None)
    try:
        plugin._client = mock_client

        await membership_monitor.metadata.callback()

        mock_api.sync_memberships.assert_called_once()
        # Expired role 5002 removed
        mock_app.rest.remove_role_from_member.assert_called_once_with(10, 111111, 5002)
        # Active role 5001 added
        mock_app.rest.add_role_to_member.assert_called_once_with(10, 111111, 5001)
        # Link role 9999 was NOT removed
        for call_args in mock_app.rest.remove_role_from_member.call_args_list:
            assert call_args[0][2] != 9999
    finally:
        plugin._client = orig_client

