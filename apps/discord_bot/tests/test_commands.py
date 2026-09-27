import pytest
from unittest.mock import MagicMock, AsyncMock, patch
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

    plugin._client.model.api.set_bot_config.assert_any_call("LINK_ROLE_ID", "112233")
    plugin._client.model.api.set_bot_config.assert_any_call("GUILD_ID", "987654321")
    mock_member_1.add_role.assert_called_once_with(112233, reason="Rol de vinculación asignado retroactivamente (/role set_link)")
    mock_member_2.add_role.assert_not_called()
    ctx.respond.assert_called_once()
    assert "Rol de vinculación configurado" in ctx.respond.call_args[0][0]
    ctx.edit.assert_called_once()
    edit_text = ctx.edit.call_args[1]["content"]
    assert "1 rol(es) asignado(s)" in edit_text
    assert "1 ya lo tenían" in edit_text


@pytest.mark.asyncio
async def test_roles_set_link_plural_command_alias():
    from src.plugins.config import RolesSetLink, plugin

    ctx = MagicMock()
    ctx.guild_id = 123456
    ctx.defer = AsyncMock()
    ctx.respond = AsyncMock()

    mock_role = MagicMock()
    mock_role.id = 887766
    mock_role.is_managed = False

    cmd = getattr(RolesSetLink, "metadata").owner()
    cmd.rol = mock_role

    plugin._client = MagicMock()
    plugin._client.model.api.set_bot_config = AsyncMock()
    plugin._client.model.api.get_paginated_players = AsyncMock(return_value={"total": 0, "players": []})

    with patch("src.plugins.config._sync_retroactive_link_role", new=AsyncMock(return_value=(0, 0))):
        await cmd.callback(ctx)

    plugin._client.model.api.set_bot_config.assert_any_call("LINK_ROLE_ID", "887766")
    plugin._client.model.api.set_bot_config.assert_any_call("GUILD_ID", "123456")
    ctx.respond.assert_called_once()
    assert "Rol de vinculación configurado" in ctx.respond.call_args[0][0]


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
    mock_member.role_ids = []
    mock_member.add_role = AsyncMock()
    mock_member.remove_role = AsyncMock()

    def mock_configs(k):
        if "BAN_ROLE" in k:
            return "999888"
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
    ctx.respond.assert_called_once()
    msg = ctx.respond.call_args[0][0]
    assert "Rol de baneo <@&999888> asignado a <@123456>" in msg
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
        "BAN_ROLE_DEFAULT": "999888"
    })
    plugin._client.model.api.unban_player = AsyncMock()

    await cmd.callback(ctx)

    # Asserts
    plugin._client.model.api.unban_player.assert_called_once_with("76561198000000001")
    mock_member.remove_role.assert_called_once_with(999888, reason="Desbaneado")
    ctx.respond.assert_called_once()
    msg = ctx.respond.call_args[0][0]
    assert "desbaneado y sincronizado con RCON" in msg
    assert "Se quitaron 1 rol(es) de ban" in msg


@pytest.mark.asyncio
async def test_player_link_without_params(monkeypatch):
    from src.plugins.account import LinkAccount, plugin

    cmd_cls = getattr(LinkAccount, "metadata").owner
    cmd = cmd_cls()
    cmd.steam_id = None
    cmd.usuario = None

    ctx = MagicMock()
    ctx.user.id = 111222333
    ctx.user.mention = "<@111222333>"
    ctx.guild_id = 999888
    ctx.defer = AsyncMock()
    ctx.respond = AsyncMock()

    mock_row = MagicMock()
    ctx.app.rest.build_message_action_row.return_value = mock_row

    plugin._client = MagicMock()
    plugin._client.model.api.api_key = "test_key"
    plugin._client.model.public_api_url = "http://test-server:8000"

    await cmd.callback(ctx)

    ctx.respond.assert_called_once()
    kwargs = ctx.respond.call_args[1]
    assert kwargs.get("ephemeral") is True
    assert "embed" in kwargs
    assert kwargs["embed"].title == "🎮 Vinculación con Steam"
    mock_row.add_link_button.assert_called_once()
    link_url = mock_row.add_link_button.call_args[0][0]
    assert "http://test-server:8000/api/v1/auth/steam/login?token=" in link_url


@pytest.mark.asyncio
async def test_player_link_with_params_restricted(monkeypatch):
    from src.plugins.account import LinkAccount, plugin

    cmd_cls = getattr(LinkAccount, "metadata").owner
    cmd = cmd_cls()
    cmd.steam_id = "76561198000000001"
    cmd.usuario = None

    ctx = MagicMock()
    ctx.user.id = 111222333
    ctx.defer = AsyncMock()
    ctx.respond = AsyncMock()

    # Non-admin
    monkeypatch.setattr("src.plugins.account.check_is_admin", AsyncMock(return_value=False))

    await cmd.callback(ctx)

    ctx.respond.assert_called_once()
    msg = ctx.respond.call_args[0][0]
    assert "La vinculación manual con Steam ID está reservada para administradores" in msg


@pytest.mark.asyncio
async def test_player_link_channel_admin(monkeypatch):
    from src.plugins.account import LinkChannel, plugin

    cmd_cls = getattr(LinkChannel, "metadata").owner
    cmd = cmd_cls()
    cmd.canal = None

    ctx = MagicMock()
    ctx.channel_id = 444555666
    ctx.defer = AsyncMock()
    ctx.respond = AsyncMock()
    ctx.app.rest.create_message = AsyncMock()

    mock_row = MagicMock()
    ctx.app.rest.build_message_action_row.return_value = mock_row

    plugin._client = MagicMock()
    plugin._client.model.api.get_bot_config = AsyncMock(return_value=None)
    plugin._client.model.api.set_bot_config = AsyncMock()

    monkeypatch.setattr("src.plugins.account.check_is_admin", AsyncMock(return_value=True))

    await cmd.callback(ctx)

    ctx.app.rest.create_message.assert_called_once()
    target_channel = ctx.app.rest.create_message.call_args[0][0]
    assert target_channel == 444555666
    mock_row.add_interactive_button.assert_called_once()
    assert mock_row.add_interactive_button.call_args[0][1] == "btn_start_steam_link"
    assert "Panel de vinculación publicado exitosamente" in ctx.respond.call_args[0][0]


@pytest.mark.asyncio
async def test_player_profile_admin_vs_player(monkeypatch):
    from src.plugins.account import Profile, plugin

    cmd_cls = getattr(Profile, "metadata").owner
    
    player_data = {
        "steam_id": "76561198058686447",
        "in_game_name": "Fr4nc0",
        "discord_id": "111222333",
        "active_role": "VIP",
        "special_roles": ["Fundador"],
        "observations": "Notas privadas de staff",
        "active_memberships": [{"type": "VIP_COMUN", "end_time": "2026-11-10T03:00:00+00:00"}]
    }

    plugin._client = MagicMock()
    plugin._client.model.api.get_player_by_discord = AsyncMock(return_value={"steam_id": "76561198058686447"})
    plugin._client.model.api.get_player_by_steam = AsyncMock(return_value=player_data)
    plugin._client.model.api.get_player_historical_stats = AsyncMock(return_value={
        "matches_played": 10, "total_kills": 20, "total_deaths": 5, "total_cash": 1000
    })

    # 1. Non-admin user querying profile (self)
    cmd = cmd_cls()
    cmd.usuario = None
    cmd.steam_id = None
    ctx = MagicMock()
    ctx.user.id = 111222333
    ctx.defer = AsyncMock()
    ctx.respond = AsyncMock()

    monkeypatch.setattr("src.plugins.account.check_is_admin", AsyncMock(return_value=False))

    await cmd.callback(ctx)

    ctx.respond.assert_called_once()
    embed = ctx.respond.call_args[1]["embed"]
    field_names = [f.name for f in embed.fields]
    assert "⭐ Rango RCON" not in field_names
    assert "📝 Observaciones Internas" not in field_names
    assert "🏷️ Roles Especiales" in field_names
    special_field = next(f for f in embed.fields if f.name == "🏷️ Roles Especiales")
    assert "Fundador" in special_field.value

    # 2. Admin querying profile
    ctx.respond.reset_mock()
    monkeypatch.setattr("src.plugins.account.check_is_admin", AsyncMock(return_value=True))

    await cmd.callback(ctx)

    ctx.respond.assert_called_once()
    embed_admin = ctx.respond.call_args[1]["embed"]
    admin_field_names = [f.name for f in embed_admin.fields]
    assert "⭐ Rango RCON" in admin_field_names
    assert "📝 Observaciones Internas" in admin_field_names
    rcon_field = next(f for f in embed_admin.fields if f.name == "⭐ Rango RCON")
    assert rcon_field.value == "VIP"
    obs_field = next(f for f in embed_admin.fields if f.name == "📝 Observaciones Internas")
    assert "Notas privadas de staff" in obs_field.value


@pytest.mark.asyncio
async def test_membership_sync_command(monkeypatch):
    from src.plugins.memberships import ForceSyncMemberships, plugin
    
    cmd_cls = getattr(ForceSyncMemberships, "metadata").owner
    cmd = cmd_cls()
    
    ctx = MagicMock()
    ctx.guild_id = 999
    ctx.app = MagicMock()
    ctx.defer = AsyncMock()
    ctx.respond = AsyncMock()
    plugin._client = MagicMock()

    mock_stats = {
        "success": True,
        "active_rcon_slots": 141,
        "expired_count": 2,
        "users_checked": 50,
        "roles_added": 3,
        "roles_removed": 1,
        "whitelist_skipped": 1
    }
    
    monkeypatch.setattr(
        "src.plugins.tasks.execute_membership_sync",
        AsyncMock(return_value=mock_stats)
    )

    await cmd.callback(ctx)

    ctx.defer.assert_called_once()
    ctx.respond.assert_called_once()
    embed = ctx.respond.call_args[1]["embed"]
    assert "Sincronización Completa" in embed.title
    field_names = [f.name for f in embed.fields]
    assert "🎮 Slots Reservados RCON" in field_names
    assert "⏰ Membresías Expiradas" in field_names
    assert "➕ Roles Añadidos" in field_names
    assert "➖ Roles Removidos" in field_names
    assert "🛡️ Whitelist" in field_names


@pytest.mark.asyncio
async def test_role_commands_and_autocompletes():
    from src.plugins.config import GiveRole, RemoveRole, autocomplete_db_roles, plugin as cfg_plugin
    from src.plugins.database import (
        DbAddSpecialRole,
        DbRemoveSpecialRole,
        PlayerSetRole,
        PlayerRemoveRole,
        autocomplete_special_roles,
        plugin as db_plugin
    )

    mock_roles = [
        {"code": "VIP_COMUN", "name": "VIP Común", "role_type": "VIP", "discord_role_id": "111"},
        {"code": "FUNDADOR", "name": "Fundador", "role_type": "SPECIAL", "discord_role_id": "222"},
        {"code": "STAFF", "name": "Staff Matefield", "role_type": "SYSTEM", "discord_role_id": "333"},
    ]

    mock_api = MagicMock()
    mock_api.get_all_roles = AsyncMock(return_value=mock_roles)
    mock_api.get_player_by_discord = AsyncMock(return_value={"steam_id": "76561198000000001"})
    mock_api.add_special_role = AsyncMock()
    mock_api.remove_special_role = AsyncMock()

    cfg_plugin._client = MagicMock()
    cfg_plugin.model.api = mock_api
    db_plugin._client = MagicMock()
    db_plugin.model.api = mock_api

    # 1. Test autocomplete_db_roles (shows all roles with types)
    auto_opt = MagicMock(value="")
    ac_ctx = MagicMock()
    all_res = await autocomplete_db_roles(ac_ctx, auto_opt)
    assert len(all_res) == 3
    assert ("Fundador (FUNDADOR) [SPECIAL]", "FUNDADOR") in all_res
    assert ("VIP Común (VIP_COMUN) [VIP]", "VIP_COMUN") in all_res

    # 2. Test autocomplete_special_roles (ONLY shows role_type == SPECIAL)
    sp_res = await autocomplete_special_roles(ac_ctx, auto_opt)
    assert len(sp_res) == 1
    assert sp_res[0] == ("Fundador (FUNDADOR)", "FUNDADOR")

    # 3. Test /roles give (GiveRole)
    give_cmd = getattr(GiveRole, "metadata").owner()
    give_cmd.usuario = MagicMock(id=123, mention="<@123>")
    give_cmd.rol = "STAFF"
    ctx = MagicMock(guild_id=888, defer=AsyncMock(), respond=AsyncMock())
    ctx.app.rest.add_role_to_member = AsyncMock()

    await give_cmd.callback(ctx)
    mock_api.add_special_role.assert_awaited_with("76561198000000001", "STAFF")
    ctx.app.rest.add_role_to_member.assert_awaited_with(888, 123, 333)
    assert "Rol `STAFF` asignado" in ctx.respond.call_args[0][0]

    # 4. Test /roles remove (RemoveRole)
    remove_cmd = getattr(RemoveRole, "metadata").owner()
    remove_cmd.usuario = MagicMock(id=123, mention="<@123>")
    remove_cmd.rol = "STAFF"
    ctx.reset_mock()
    ctx.app.rest.remove_role_from_member = AsyncMock()

    await remove_cmd.callback(ctx)
    mock_api.remove_special_role.assert_awaited_with("76561198000000001", "STAFF")
    ctx.app.rest.remove_role_from_member.assert_awaited_with(888, 123, 333)
    assert "Rol `STAFF` removido" in ctx.respond.call_args[0][0]

    # 5. Test /player set_role (PlayerSetRole)
    pset_cmd = getattr(PlayerSetRole, "metadata").owner()
    pset_cmd.usuario = MagicMock(id=456, mention="<@456>")
    pset_cmd.rol = "VIP_COMUN"
    ctx.reset_mock()
    ctx.app.rest.add_role_to_member = AsyncMock()

    await pset_cmd.callback(ctx)
    mock_api.add_special_role.assert_awaited_with("76561198000000001", "VIP_COMUN")
    ctx.app.rest.add_role_to_member.assert_awaited_with(888, 456, 111)

    # 6. Test /player remove_role (PlayerRemoveRole)
    prem_cmd = getattr(PlayerRemoveRole, "metadata").owner()
    prem_cmd.usuario = MagicMock(id=456, mention="<@456>")
    prem_cmd.rol = "VIP_COMUN"
    ctx.reset_mock()
    ctx.app.rest.remove_role_from_member = AsyncMock()

    await prem_cmd.callback(ctx)
    mock_api.remove_special_role.assert_awaited_with("76561198000000001", "VIP_COMUN")
    ctx.app.rest.remove_role_from_member.assert_awaited_with(888, 456, 111)

    # 7. Test /special_role add rejecting non-SPECIAL role
    sp_add_cmd = getattr(DbAddSpecialRole, "metadata").owner()
    sp_add_cmd.usuario = MagicMock(id=789, mention="<@789>")
    sp_add_cmd.rol_especial = "STAFF"  # Not a SPECIAL role
    ctx.reset_mock()

    await sp_add_cmd.callback(ctx)
    assert "Debes seleccionar un rol registrado con categoría `SPECIAL`" in ctx.respond.call_args[0][0]

    # 8. Test /special_role add accepting SPECIAL role
    sp_add_cmd.rol_especial = "FUNDADOR"
    ctx.reset_mock()
    ctx.app.rest.add_role_to_member = AsyncMock()

    await sp_add_cmd.callback(ctx)
    mock_api.add_special_role.assert_awaited_with("76561198000000001", "FUNDADOR")
    ctx.app.rest.add_role_to_member.assert_awaited_with(888, 789, 222)
    assert "Rol especial `Fundador` (`FUNDADOR`) añadido" in ctx.respond.call_args[0][0]


@pytest.mark.asyncio
async def test_rewards_plugin_commands():
    from src.plugins.rewards import (
        RewardsBalance,
        RewardsCatalog,
        RewardsClaim,
        RewardsSetThreshold,
        RewardsSetRate,
        RewardsVerifyClaim,
        RewardsDeliverClaim,
        RewardsRefundClaim,
        RewardsGivePoints,
        RewardsAddItem,
        plugin as rewards_plugin,
    )

    mock_api = MagicMock()
    mock_api.get_player_rewards_balance = AsyncMock(return_value={
        "steam_id": "76561198000000001",
        "discord_id": "123456",
        "in_game_name": "ProGamer",
        "reward_points": 75,
        "total_seeding_minutes": 150,
        "claims": [{"reward_name": "Key Game", "claim_code": "MF-AAAA-BBBB", "status": "PENDING"}]
    })
    mock_api.get_rewards_catalog = AsyncMock(return_value=[
        {"code": "VIP_MONTH", "name": "VIP 30d", "cost_points": 60, "delivery_type": "AUTOMATIC", "description": "Acceso VIP"},
        {"code": "STEAM_KEY", "name": "Key Game", "cost_points": 100, "delivery_type": "MANUAL_TICKET", "description": "Ticket key"}
    ])
    mock_api.claim_reward = AsyncMock(return_value={
        "claim_code": "MF-1111-2222",
        "reward_name": "VIP 30d",
        "cost_points": 60,
        "remaining_points": 15,
        "delivery": {"delivery_type": "AUTOMATIC"}
    })
    mock_api.set_bot_config = AsyncMock(return_value={"ok": True})
    mock_api.verify_reward_claim = AsyncMock(return_value={
        "claim_code": "MF-1111-2222",
        "status": "PENDING",
        "reward_code": "STEAM_KEY",
        "reward_name": "Key Game",
        "points_spent": 100,
        "steam_id": "76561198000000001",
        "discord_id": "123456",
        "claimed_at": "2026-09-27T12:00:00"
    })
    mock_api.deliver_reward_claim = AsyncMock(return_value={"ok": True, "message": "Entregado"})
    mock_api.refund_reward_claim = AsyncMock(return_value={"ok": True, "message": "Reembolsado"})
    mock_api.give_reward_points = AsyncMock(return_value={"ok": True, "steam_id": "76561198000000001", "new_balance": 125})
    mock_api.create_or_update_reward_item = AsyncMock(return_value={"ok": True, "message": "Item creado"})

    rewards_plugin._client = MagicMock()
    rewards_plugin.model.api = mock_api

    ctx = MagicMock()
    ctx.defer = AsyncMock()
    ctx.respond = AsyncMock()
    ctx.user = MagicMock(id=123456, mention="<@123456>")

    # 1. Test /rewards balance
    bal_cmd = getattr(RewardsBalance, "metadata").owner()
    bal_cmd.usuario = None
    await bal_cmd.callback(ctx)
    mock_api.get_player_rewards_balance.assert_awaited_with("123456")
    embed = ctx.respond.call_args[1]["embed"]
    assert "Centro de Recompensas" in embed.title

    # 2. Test /rewards catalog
    cat_cmd = getattr(RewardsCatalog, "metadata").owner()
    ctx.reset_mock()
    await cat_cmd.callback(ctx)
    mock_api.get_rewards_catalog.assert_awaited_with(only_active=True)
    embed = ctx.respond.call_args[1]["embed"]
    assert "Catálogo de Recompensas" in embed.title

    # 3. Test /rewards claim
    claim_cmd = getattr(RewardsClaim, "metadata").owner()
    claim_cmd.recompensa = "VIP_MONTH"
    ctx.reset_mock()
    await claim_cmd.callback(ctx)
    mock_api.claim_reward.assert_awaited_with("123456", "VIP_MONTH")
    embed = ctx.respond.call_args[1]["embed"]
    assert "Canje Exitoso" in embed.title

    # 4. Test /rewards admin set_threshold
    thresh_cmd = getattr(RewardsSetThreshold, "metadata").owner()
    thresh_cmd.limite = 25
    ctx.reset_mock()
    await thresh_cmd.callback(ctx)
    mock_api.set_bot_config.assert_awaited_with("SEEDING_MIN_PLAYERS", "25")

    # 5. Test /rewards admin set_rate
    rate_cmd = getattr(RewardsSetRate, "metadata").owner()
    rate_cmd.minutos = 45
    ctx.reset_mock()
    await rate_cmd.callback(ctx)
    mock_api.set_bot_config.assert_awaited_with("SEEDING_MINUTES_PER_POINT", "45")

    # 6. Test /rewards admin verify
    verify_cmd = getattr(RewardsVerifyClaim, "metadata").owner()
    verify_cmd.codigo_canje = "MF-1111-2222"
    ctx.reset_mock()
    await verify_cmd.callback(ctx)
    mock_api.verify_reward_claim.assert_awaited_with("MF-1111-2222")

    # 7. Test /rewards admin deliver
    deliver_cmd = getattr(RewardsDeliverClaim, "metadata").owner()
    deliver_cmd.codigo_canje = "MF-1111-2222"
    deliver_cmd.notas = "Entregado en ticket #12"
    ctx.reset_mock()
    await deliver_cmd.callback(ctx)
    mock_api.deliver_reward_claim.assert_awaited_with("MF-1111-2222", delivered_by=str(ctx.user), notes="Entregado en ticket #12")

    # 8. Test /rewards admin refund
    refund_cmd = getattr(RewardsRefundClaim, "metadata").owner()
    refund_cmd.codigo_canje = "MF-1111-2222"
    refund_cmd.motivo = "Sin stock"
    ctx.reset_mock()
    await refund_cmd.callback(ctx)
    mock_api.refund_reward_claim.assert_awaited_with("MF-1111-2222", refunded_by=str(ctx.user), reason="Sin stock")

    # 9. Test /rewards admin give_points
    give_cmd = getattr(RewardsGivePoints, "metadata").owner()
    give_cmd.usuario = None
    give_cmd.steam_id = "76561198000000001"
    give_cmd.puntos = 50
    give_cmd.motivo = "Evento de navidad"
    ctx.reset_mock()
    await give_cmd.callback(ctx)
    mock_api.give_reward_points.assert_awaited_with("76561198000000001", 50, "Evento de navidad")

    # 10. Test /rewards admin add_item
    add_cmd = getattr(RewardsAddItem, "metadata").owner()
    add_cmd.codigo = "VIP_15D"
    add_cmd.nombre = "VIP 15 Días"
    add_cmd.costo = 30
    add_cmd.tipo_entrega = "AUTOMATIC"
    add_cmd.tipo_recompensa = "MEMBERSHIP"
    add_cmd.valor = "VIP"
    add_cmd.duracion_dias = 15
    add_cmd.descripcion = "Membresía corta"
    ctx.reset_mock()
    await add_cmd.callback(ctx)
    mock_api.create_or_update_reward_item.assert_awaited_with(
        code="VIP_15D",
        name="VIP 15 Días",
        cost_points=30,
        delivery_type="AUTOMATIC",
        reward_type="MEMBERSHIP",
        reward_value="VIP",
        duration_days=15,
        description="Membresía corta",
        is_active=True,
    )






