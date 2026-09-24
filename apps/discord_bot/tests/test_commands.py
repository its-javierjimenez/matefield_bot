import pytest
from unittest.mock import MagicMock, AsyncMock
from src.plugins.memberships import build_player_memberships_view
from src.api_client import APIClient


def test_build_player_memberships_view_all_fields():
    app_mock = MagicMock()
    app_mock.rest.build_message_action_row.return_value = MagicMock()

    memberships_data = [
        {
            "id": 42,
            "steam_id": "76561198000000001",
            "type": "VIP_COMUN",
            "is_active": True,
            "start_date": "2026-09-01T12:00:00+00:00",
            "end_date": "2026-10-01T12:00:00+00:00",
            "special_role": "ADMIN",
            "special_role_id": 999999,
            "rcon_sync_status": "SUCCESS"
        }
    ]

    embed, components = build_player_memberships_view(
        app_mock,
        usuario_id=123456789,
        memberships=memberships_data,
        page=1,
        total=1,
        limit=5
    )

    assert embed.title is not None and "Historial de Membresías" in embed.title
    assert len(embed.fields) == 1
    field = embed.fields[0]

    # Verify that all table fields are rendered in the field
    assert "Membresía #42" in field.name
    assert "VIP_COMUN" in field.name
    assert "🟢 Activa" in field.value
    assert "is_active=True" in field.value
    assert "76561198000000001" in field.value
    assert "2026-09-01 12:00:00" in field.value
    assert "2026-10-01 12:00:00" in field.value
    assert "999999" in field.value
    assert "SUCCESS" in field.value


@pytest.mark.asyncio
async def test_api_client_get_paginated_memberships_url(monkeypatch):
    client = APIClient("http://test-server", "secret-key")

    requested_url: str | None = None

    async def mock_request(method, endpoint, **kwargs):
        nonlocal requested_url
        requested_url = endpoint
        return {"page": 1, "limit": 5, "total": 0, "memberships": []}

    monkeypatch.setattr(client, "_request", mock_request)

    res = await client.get_paginated_memberships(page=2, limit=5, discord_id="123456")
    assert requested_url is not None and "/api/v1/db/memberships?page=2&limit=5&discord_id=123456" in requested_url
    assert res["memberships"] == []


@pytest.mark.asyncio
async def test_role_set_link_retroactive_grant():
    from src.plugins.config import RoleSetLink, plugin

    ctx = MagicMock()
    ctx.guild_id = 987654321
    ctx.defer = AsyncMock()
    ctx.respond = AsyncMock()

    mock_role = MagicMock()
    mock_role.id = 112233
    mock_role.is_managed = False

    cmd = getattr(RoleSetLink, "metadata").owner()
    cmd.rol = mock_role

    mock_member_1 = MagicMock()
    mock_member_1.role_ids = [445566]
    mock_member_1.add_role = AsyncMock()

    mock_member_2 = MagicMock()
    mock_member_2.role_ids = [112233]  # already had it
    mock_member_2.add_role = AsyncMock()

    def get_member(guild_id, user_id):
        if user_id == 1001:
            return mock_member_1
        if user_id == 1002:
            return mock_member_2
        return None

    plugin._client = MagicMock()
    plugin._client.app.cache.get_member.side_effect = get_member
    plugin._client.model.api.set_bot_config = AsyncMock()
    plugin._client.model.api.get_paginated_players = AsyncMock(return_value={
        "total": 2,
        "page": 1,
        "limit": 100,
        "players": [
            {"steam_id": "s1", "discord_id": "1001"},
            {"steam_id": "s2", "discord_id": "1002"}
        ]
    })

    ctx.edit = AsyncMock()

    task = await cmd.callback(ctx)
    if task:
        await task

    plugin._client.model.api.set_bot_config.assert_called_once_with("LINK_ROLE_ID", "112233")
    mock_member_1.add_role.assert_called_once_with(112233, reason="Rol de vinculación asignado retroactivamente (/role set_link)")
    mock_member_2.add_role.assert_not_called()
    ctx.respond.assert_called_once()
    assert "Rol de vinculación configurado" in ctx.respond.call_args[0][0]
    ctx.edit.assert_called_once()
    edit_text = ctx.edit.call_args[1]["content"]
    assert "1 rol(es) asignado(s)" in edit_text
    assert "1 ya lo tenían" in edit_text


@pytest.mark.asyncio
async def test_unlink_account_permissions(monkeypatch):
    from src.plugins.account import UnlinkAccount, plugin

    cmd_cls = getattr(UnlinkAccount, "metadata").owner

    # 1. Non-admin trying to unlink someone else -> blocked
    cmd = cmd_cls()
    other_user = MagicMock()
    other_user.id = 9999
    cmd.usuario = other_user

    ctx = MagicMock()
    ctx.user.id = 1234
    ctx.defer = AsyncMock()
    ctx.respond = AsyncMock()

    async def mock_is_admin_false(c):
        return False

    monkeypatch.setattr("src.plugins.account.check_is_admin", mock_is_admin_false)

    await cmd.callback(ctx)
    ctx.respond.assert_called_once_with("❌ Solo los administradores pueden desvincular a otros usuarios.")

    # 2. Regular user unlinking themselves (no usuario) -> success
    cmd_self = cmd_cls()
    cmd_self.usuario = None

    ctx_self = MagicMock()
    ctx_self.guild_id = None
    ctx_self.user.id = 1234
    ctx_self.defer = AsyncMock()
    ctx_self.respond = AsyncMock()

    plugin._client = MagicMock()
    plugin._client.model.api.unlink_account = AsyncMock()

    await cmd_self.callback(ctx_self)
    plugin._client.model.api.unlink_account.assert_called_once_with("1234")
    assert "Tu cuenta de Discord ha sido desvinculada" in ctx_self.respond.call_args[0][0]

    # 3. Admin unlinking someone else -> success
    cmd_admin = cmd_cls()
    target_user = MagicMock()
    target_user.id = 8888
    target_user.mention = "<@8888>"
    cmd_admin.usuario = target_user

    ctx_admin = MagicMock()
    ctx_admin.guild_id = None
    ctx_admin.user.id = 1111
    ctx_admin.defer = AsyncMock()
    ctx_admin.respond = AsyncMock()

    async def mock_is_admin_true(c):
        return True

    monkeypatch.setattr("src.plugins.account.check_is_admin", mock_is_admin_true)
    plugin._client.model.api.unlink_account = AsyncMock()

    await cmd_admin.callback(ctx_admin)
    plugin._client.model.api.unlink_account.assert_called_once_with("8888")
    assert "ha sido desvinculada y sus roles revocados" in ctx_admin.respond.call_args[0][0]


@pytest.mark.asyncio
async def test_ban_player_solo_discord():
    from src.plugins.admin import BanPlayer, plugin

    cmd_cls = getattr(BanPlayer, "metadata").owner

    # 1. solo_discord = True -> Assigns Discord role, removes unset_ban role, calls api.ban_player(..., solo_discord=True)
    cmd = cmd_cls()
    cmd.steam_id = "76561198000000001"
    cmd.usuario = None
    cmd.reason = "Insultos en chat de Discord"
    cmd.dias = 0
    cmd.solo_discord = True

    ctx = MagicMock()
    ctx.guild_id = 987654321
    ctx.defer = AsyncMock()
    ctx.respond = AsyncMock()

    mock_member = MagicMock()
    mock_member.role_ids = [777888]  # Already has the unset_ban role
    mock_member.add_role = AsyncMock()
    mock_member.remove_role = AsyncMock()

    def mock_configs(k):
        if "BAN_ROLE" in k:
            return "999888"
        if k == "BAN_UNSET_ROLE_ID":
            return "777888"
        return None

    plugin._client = MagicMock()
    plugin._client.app.cache.get_member.return_value = mock_member
    plugin._client.model.api.get_player_by_steam = AsyncMock(return_value={"steam_id": "76561198000000001", "discord_id": "123456"})
    plugin._client.model.api.get_bot_config = AsyncMock(side_effect=mock_configs)
    plugin._client.model.api.ban_player = AsyncMock()

    await cmd.callback(ctx)

    # Asserts
    plugin._client.model.api.ban_player.assert_called_once_with("76561198000000001", "Insultos en chat de Discord", 0, solo_discord=True)
    mock_member.add_role.assert_called_once_with(999888, reason="Baneo Discord: Insultos en chat de Discord (permanentemente)")
    mock_member.remove_role.assert_called_once_with(777888, reason="Baneo Discord: rol revocado (permanentemente)")
    ctx.respond.assert_called_once()
    msg = ctx.respond.call_args[0][0]
    assert "Rol de baneo <@&999888> asignado a <@123456>" in msg
    assert "Rol <@&777888> removido" in msg
    assert "Sanción aplicada únicamente en Discord (no se sincronizó con RCON)" in msg

    # 1b. solo_discord = True on unlinked player -> saves in DB, informs that roles apply on link
    cmd_unlinked = cmd_cls()
    cmd_unlinked.steam_id = "76561198000000099"
    cmd_unlinked.usuario = None
    cmd_unlinked.reason = "Griefing"
    cmd_unlinked.dias = 0
    cmd_unlinked.solo_discord = True

    ctx_unlinked = MagicMock()
    ctx_unlinked.guild_id = 987654321
    ctx_unlinked.defer = AsyncMock()
    ctx_unlinked.respond = AsyncMock()

    plugin._client.model.api.get_player_by_steam = AsyncMock(return_value=None)
    plugin._client.model.api.ban_player.reset_mock()

    await cmd_unlinked.callback(ctx_unlinked)

    plugin._client.model.api.ban_player.assert_called_once_with("76561198000000099", "Griefing", 0, solo_discord=True)
    assert "los roles se aplicarán automáticamente cuando vincule su cuenta" in ctx_unlinked.respond.call_args[0][0]

    # 2. solo_discord = False -> Calls api.ban_player and syncs
    cmd_normal = cmd_cls()
    cmd_normal.steam_id = "76561198000000001"
    cmd_normal.usuario = None
    cmd_normal.reason = "Cheat/Aimbot"
    cmd_normal.dias = 7
    cmd_normal.solo_discord = False

    ctx_normal = MagicMock()
    ctx_normal.guild_id = 987654321
    ctx_normal.defer = AsyncMock()
    ctx_normal.respond = AsyncMock()

    mock_member.role_ids = [777888]
    mock_member.add_role.reset_mock()
    mock_member.remove_role.reset_mock()
    plugin._client.model.api.ban_player.reset_mock()
    plugin._client.model.api.get_player_by_steam = AsyncMock(return_value={"steam_id": "76561198000000001", "discord_id": "123456"})

    await cmd_normal.callback(ctx_normal)

    plugin._client.model.api.ban_player.assert_called_once_with("76561198000000001", "Cheat/Aimbot", 7, solo_discord=False)
    mock_member.add_role.assert_called_once_with(999888, reason="Baneado por 7 días")
    mock_member.remove_role.assert_called_once_with(777888, reason="Baneado: rol revocado (por 7 días)")
    assert "baneado por 7 días" in ctx_normal.respond.call_args[0][0]

    # 3. Ban by @user directly (resolves linked Steam ID)
    cmd_user = cmd_cls()
    mock_target_user = MagicMock()
    mock_target_user.id = 555666
    cmd_user.usuario = mock_target_user
    cmd_user.steam_id = None
    cmd_user.reason = "Toxic behavior"
    cmd_user.dias = 0
    cmd_user.solo_discord = False

    ctx_user = MagicMock()
    ctx_user.guild_id = 987654321
    ctx_user.defer = AsyncMock()
    ctx_user.respond = AsyncMock()

    mock_member.role_ids = []
    mock_member.add_role.reset_mock()
    plugin._client.model.api.ban_player.reset_mock()
    plugin._client.model.api.get_player_by_discord = AsyncMock(return_value={"steam_id": "76561198999999999", "discord_id": "555666"})

    await cmd_user.callback(ctx_user)

    plugin._client.model.api.ban_player.assert_called_once_with("76561198999999999", "Toxic behavior", 0, solo_discord=False)
    mock_member.add_role.assert_called_once_with(999888, reason="Baneado permanentemente")
    assert "Jugador `76561198999999999` (<@555666>) baneado permanentemente" in ctx_user.respond.call_args[0][0]

    # 4. Ban by typing mention string <@555666> in steam_id option
    cmd_mention = cmd_cls()
    cmd_mention.usuario = None
    cmd_mention.steam_id = "<@555666>"
    cmd_mention.reason = "Spamming"
    cmd_mention.dias = 1
    cmd_mention.solo_discord = False

    ctx_mention = MagicMock()
    ctx_mention.guild_id = 987654321
    ctx_mention.defer = AsyncMock()
    ctx_mention.respond = AsyncMock()

    mock_member.role_ids = []
    mock_member.add_role.reset_mock()
    plugin._client.model.api.ban_player.reset_mock()

    await cmd_mention.callback(ctx_mention)

    plugin._client.model.api.ban_player.assert_called_once_with("76561198999999999", "Spamming", 1, solo_discord=False)
    mock_member.add_role.assert_called_once_with(999888, reason="Baneado por 1 días")


@pytest.mark.asyncio
async def test_unban_player_role_switch():
    from src.plugins.admin import UnbanStandalone, plugin

    cmd_cls = getattr(UnbanStandalone, "metadata").owner
    cmd = cmd_cls()
    cmd.steam_id = "76561198000000001"
    cmd.usuario = None
    cmd.solo_discord = False

    ctx = MagicMock()
    ctx.guild_id = 987654321
    ctx.defer = AsyncMock()
    ctx.respond = AsyncMock()

    mock_member = MagicMock()
    mock_member.role_ids = [999888]  # Currently has ban role
    mock_member.add_role = AsyncMock()
    mock_member.remove_role = AsyncMock()

    plugin._client = MagicMock()
    plugin._client.app.cache.get_member.return_value = mock_member
    plugin._client.model.api.get_player_by_steam = AsyncMock(return_value={"steam_id": "76561198000000001", "discord_id": "123456"})
    plugin._client.model.api.get_bot_configs = AsyncMock(return_value={
        "BAN_ROLE_DEFAULT": "999888",
        "BAN_UNSET_ROLE_ID": "777888"
    })
    plugin._client.model.api.unban_player = AsyncMock()

    await cmd.callback(ctx)

    # Asserts
    plugin._client.model.api.unban_player.assert_called_once_with("76561198000000001")
    mock_member.remove_role.assert_called_once_with(999888, reason="Desbaneado")
    mock_member.add_role.assert_called_once_with(777888, reason="Desbaneado: rol restituido")
    ctx.respond.assert_called_once()
    msg = ctx.respond.call_args[0][0]
    assert "desbaneado y sincronizado con RCON" in msg
    assert "Se quitaron 1 rol(es) de ban" in msg
    assert "Rol <@&777888> restituido" in msg


@pytest.mark.asyncio
async def test_role_unset_ban_config():
    from src.plugins.config import RoleUnsetBan, plugin

    cmd_cls = getattr(RoleUnsetBan, "metadata").owner
    cmd = cmd_cls()
    mock_role = MagicMock()
    mock_role.id = 777888
    cmd.rol = mock_role

    ctx = MagicMock()
    ctx.defer = AsyncMock()
    ctx.respond = AsyncMock()

    plugin._client = MagicMock()
    plugin._client.model.api.set_bot_config = AsyncMock()

    await cmd.callback(ctx)

    plugin._client.model.api.set_bot_config.assert_called_once_with("BAN_UNSET_ROLE_ID", "777888")
    assert "Rol de desbaneo configurado a <@&777888>" in ctx.respond.call_args[0][0]

