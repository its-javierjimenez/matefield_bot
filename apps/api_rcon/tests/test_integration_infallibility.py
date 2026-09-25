import asyncio
from datetime import datetime, timezone, timedelta
import pytest
from httpx import AsyncClient
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from wardogs_schemas import v1 as schemas

from src.connections.databases.db import Player, Membership, Ban, Role, PlayerRole
import src.connections.apis.rcon as rcon_module
from src.connections.apis.rcon import RCONClient, _update_ini_array
from src.modules.v1.services.bans_service import BansService
from src.modules.v1.services.memberships_service import MembershipsService
from src.modules.v1.services.server_service import ServerService


@pytest.mark.asyncio
async def test_unban_player_prevents_resurrection_and_cleans_rcon(client: AsyncClient, session: AsyncSession, mocker):
    """
    Infallibility Test:
    When a player is unbanned in DB, subsequent sync_bans MUST NOT resurrect them
    even if RCON still temporarily reports them, and MUST send DELETE to RCON.
    """
    mock_unban_rcon = mocker.patch.object(RCONClient, "unban_player", return_value=None)
    mock_sync_banned = mocker.patch.object(RCONClient, "sync_banned_slots", return_value=None)

    # 1. Player is banned
    steam_id = "76561198999999001"
    ban = Ban(steam_id=steam_id, reason="Cheating", is_active=True, rcon_sync_status="SUCCESS")
    session.add(ban)
    await session.commit()

    # 2. Admin unbans player
    unban_resp = await client.post(f"/api/v1/players/{steam_id}/unban")
    assert unban_resp.status_code == 200

    await session.refresh(ban)
    assert ban.is_active is False
    # Verify RCON delete was called
    mock_unban_rcon.assert_called_with(steam_id)

    # 3. Simulate RCON still returning steam_id in get_bans()
    mocker.patch.object(RCONClient, "get_bans", return_value=[steam_id, "76561198000000002"])

    # 4. Trigger sync_bans
    sync_resp = await client.post("/api/v1/db/sync_bans")
    assert sync_resp.status_code == 200

    # 5. Verify the unbanned player was NOT resurrected as active
    all_bans_for_player = (await session.exec(select(Ban).where(Ban.steam_id == steam_id))).all()
    assert all(not b.is_active for b in all_bans_for_player)
    assert len(all_bans_for_player) == 1

    # Verify RCON unban was re-issued to purge lingering ban on server
    assert mock_unban_rcon.call_count >= 2


@pytest.mark.asyncio
async def test_concurrent_vip_and_ban_sync_atomicity(session: AsyncSession):
    """
    Infallibility Test:
    Simulate real concurrency between sync_reserved_slots (136 VIPs) and sync_banned_slots (50 bans).
    With _config_lock, neither process overwrites the other, and the final INI has BOTH sets intact.
    """
    base_ini = "[/Script/WDGame.WDGameSession]\nServerName=Matefield\n"
    rcon = RCONClient("http://fake:7776", "secret")

    # In-memory server simulation
    server_state = {
        "text": base_ini,
        "revision": "rev_0"
    }
    rev_counter = 0

    async def fake_get_config():
        await asyncio.sleep(0.01) # simulate network latency
        return schemas.Config1(text=server_state["text"], revision=server_state["revision"])

    async def fake_update_config(revision: str, new_text: str):
        nonlocal rev_counter
        await asyncio.sleep(0.01) # simulate server apply latency
        rev_counter += 1
        server_state["text"] = new_text
        server_state["revision"] = f"rev_{rev_counter}"
        return schemas.ConfigResult(ok=True, revision=server_state["revision"])

    rcon.get_config = fake_get_config
    rcon.update_config = fake_update_config

    vips_136 = [f"76561198000000{i:03d}" for i in range(136)]
    bans_50 = [f"76561198900000{i:03d}" for i in range(50)]

    # Run both concurrently
    await asyncio.gather(
        rcon.sync_reserved_slots(vips_136),
        rcon.sync_banned_slots(bans_50)
    )

    final_text = server_state["text"]
    reserved_lines = [l for l in final_text.split('\n') if l.startswith('.DefaultReservedPlayerIds=')]
    banned_lines = [l for l in final_text.split('\n') if l.startswith('.DefaultBannedPlayerIds=')]

    # Assert 100% preservation: 136 VIPs and 50 bans coexist with zero data loss!
    assert len(reserved_lines) == 136
    assert len(banned_lines) == 50
    assert "!DefaultReservedPlayerIds=ClearArray" in final_text
    assert "!DefaultBannedPlayerIds=ClearArray" in final_text


@pytest.mark.asyncio
async def test_e2e_tebex_purchase_to_discord_sync_payload(client: AsyncClient, session: AsyncSession, mocker):
    """
    Integration Test:
    Tebex payment.completed webhook -> DB Player & Membership -> RCON Sync -> Discord Role Mapping
    """
    mocker.patch.object(RCONClient, "sync_reserved_slots", return_value=None)
    mocker.patch.object(RCONClient, "get_reserved_slots", return_value=schemas.ReservedSlots(reservedSlots=[]))

    steam_id = "76561198888888001"
    discord_id = "123456789012345678"

    # Pre-seed linked player
    player = Player(steam_id=steam_id, discord_id=discord_id, in_game_name="TebexTester")
    session.add(player)
    await session.commit()

    webhook_payload = {
        "id": "e2e-tx-9999",
        "type": "payment.completed",
        "subject": {
            "transaction_id": "tbx-e2e-9999",
            "status": {"id": 1, "description": "Complete"},
            "price_paid": {"amount": 10.0, "currency": "USD"},
            "customer": {
                "username": steam_id,
                "email": "gamer@example.com"
            },
            "products": [
                {
                    "id": 101,
                    "name": "VIP Comun",
                    "custom": {
                        "discord_id": discord_id,
                        "steam_id": steam_id
                    }
                }
            ]
        }
    }

    # 1. Post webhook
    resp = await client.post("/api/v1/webhooks/tebex", json=webhook_payload)
    assert resp.status_code == 200

    # 2. Verify Membership in DB
    membership = (await session.exec(select(Membership).where(Membership.steam_id == steam_id))).first()
    assert membership is not None
    assert membership.is_active is True
    assert membership.membership_type == "VIP_COMUN"

    # 3. Verify sync_memberships returns Discord sync data
    sync_res = await client.post("/api/v1/db/sync_memberships")
    assert sync_res.status_code == 200
    sync_data = sync_res.json()["sync_data"]

    user_entry = next((u for u in sync_data if u["discord_id"] == discord_id), None)
    assert user_entry is not None
    assert "VIP_COMUN" in user_entry["active_memberships"]


@pytest.mark.asyncio
async def test_e2e_recurring_cancellation_preserves_active_period(client: AsyncClient, session: AsyncSession, mocker):
    """
    Integration Test:
    When recurring-payment.ended arrives for an active subscription with future end_time,
    the membership must STAY active until its end_time and not be killed prematurely.
    """
    mocker.patch.object(RCONClient, "sync_reserved_slots", return_value=None)

    steam_id = "76561198777777002"
    sub_ref = "sub-future-expiry-123"
    future_end = datetime.now(timezone.utc) + timedelta(days=20)

    player = Player(steam_id=steam_id, in_game_name="SubscriptionUser")
    membership = Membership(
        steam_id=steam_id,
        membership_type="VIP_COMUN",
        is_active=True,
        start_time=datetime.now(timezone.utc) - timedelta(days=10),
        end_time=future_end,
        tebex_subscription_id=sub_ref,
        payment_source="TEBEX"
    )
    session.add_all([player, membership])
    await session.commit()

    webhook_payload = {
        "id": "evt-sub-cancelled-early",
        "type": "recurring-payment.ended",
        "subject": {
            "reference": sub_ref,
            "status": {"id": 5, "description": "Cancelled"}
        }
    }

    resp = await client.post("/api/v1/webhooks/tebex", json=webhook_payload)
    assert resp.status_code == 200

    await session.refresh(membership)
    # MUST stay active because customer paid for the full month
    assert membership.is_active is True
    # Subscription reference cleared to prevent renewed events
    assert membership.tebex_subscription_id is None


@pytest.mark.asyncio
async def test_server_service_add_remove_reserved_slot_preserves_db_vips(session: AsyncSession, mocker):
    """
    Infallibility Test:
    add_reserved_slot and remove_reserved_slot must query active DB memberships
    and NEVER overwrite ServerSettings.ini with only the RCON in-memory list.
    """
    captured_slots = None

    async def fake_sync(slots):
        nonlocal captured_slots
        captured_slots = slots

    mocker.patch.object(RCONClient, "sync_reserved_slots", side_effect=fake_sync)

    # Seed 3 active DB VIPs
    for i in range(3):
        m = Membership(
            steam_id=f"7656119800000001{i}",
            membership_type="VIP_COMUN",
            is_active=True
        )
        session.add(m)
    await session.commit()

    # Add a new reserved slot manually
    new_slot = "76561198999999999"
    await ServerService.add_reserved_slot(new_slot, session=session)

    assert captured_slots is not None
    # All 3 seeded DB VIPs + new slot must be present!
    assert len(captured_slots) == 4
    assert new_slot in captured_slots
    assert "76561198000000010" in captured_slots

    # Remove the slot manually
    await ServerService.remove_reserved_slot(new_slot, session=session)
    assert len(captured_slots) == 3
    assert new_slot not in captured_slots
    assert "76561198000000010" in captured_slots
