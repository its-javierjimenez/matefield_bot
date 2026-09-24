import pytest
from sqlmodel import select
from src.connections.databases.db import Player, Membership, RconServer, MembershipType
from src.modules.v1.services.rcon_servers_service import RconServersService
from src.connections.apis.rcon import RCONManager, RCONClient


@pytest.mark.asyncio
async def test_membership_types_crud(client):
    # 1. List defaults and check Tebex package ID mappings
    resp = await client.get("/api/v1/membership-types")
    assert resp.status_code == 200
    types = resp.json()
    assert len(types) >= 3
    type_map = {t["code"]: t for t in types}
    assert type_map["VIP_COMUN"]["tebex_package_id"] == 7682027
    assert type_map["VIP_EXPRESS"]["tebex_package_id"] == 7682061
    assert type_map["VIP_PERMANENTE"]["tebex_package_id"] is None

    # 2. Create custom package with tebex_package_id
    create_payload = {
        "code": "VIP_SNIPER",
        "name": "VIP Sniper Especial",
        "description": "Acceso con kit sniper y slot reservado",
        "price_usd": 12.50,
        "billing_type": "RECURRING",
        "default_days": 15,
        "max_quota": 5,
        "tebex_package_id": 9999999,
        "is_active": True
    }
    resp = await client.post("/api/v1/membership-types", json=create_payload)
    assert resp.status_code == 200
    created = resp.json()["membership_type"]
    assert created["code"] == "VIP_SNIPER"
    assert created["price_usd"] == 12.50
    assert created["billing_type"] == "RECURRING"
    assert created["tebex_package_id"] == 9999999
    type_id = created["id"]

    # 3. Get by identifier (code and id)
    resp = await client.get("/api/v1/membership-types/VIP_SNIPER")
    assert resp.status_code == 200
    assert resp.json()["id"] == type_id
    assert resp.json()["tebex_package_id"] == 9999999

    resp = await client.get(f"/api/v1/membership-types/{type_id}")
    assert resp.status_code == 200
    assert resp.json()["code"] == "VIP_SNIPER"

    # 4. Update
    update_payload = {
        "price_usd": 15.00,
        "max_quota": 8,
        "tebex_package_id": 8888888
    }
    resp = await client.put(f"/api/v1/membership-types/{type_id}", json=update_payload)
    assert resp.status_code == 200
    assert resp.json()["membership_type"]["price_usd"] == 15.00
    assert resp.json()["membership_type"]["max_quota"] == 8
    assert resp.json()["membership_type"]["tebex_package_id"] == 8888888

    # 5. Delete (soft-delete)
    resp = await client.delete(f"/api/v1/membership-types/{type_id}")
    assert resp.status_code == 200

    resp = await client.get(f"/api/v1/membership-types/{type_id}")
    assert resp.json()["is_active"] is False


@pytest.mark.asyncio
async def test_payment_record_model(session):
    from src.connections.databases.db import PaymentRecord
    record = PaymentRecord(
        transaction_id="tb-test-tx-12345",
        event_type="payment.completed",
        steam_id="76561198000000001",
        discord_id="1234567890",
        package_id=7682027,
        package_name="VIP COMUN",
        amount=6.00,
        currency="USD",
        status="COMPLETED",
        raw_payload='{"test": true}'
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)

    assert record.id is not None
    assert record.transaction_id == "tb-test-tx-12345"
    assert record.status == "COMPLETED"

    # Duplicate transaction_id should fail
    duplicate = PaymentRecord(
        transaction_id="tb-test-tx-12345",
        event_type="payment.completed",
        raw_payload='{}'
    )
    session.add(duplicate)
    with pytest.raises(Exception):
        await session.commit()
    await session.rollback()


@pytest.mark.asyncio
async def test_membership_type_defaults_and_quota_enforcement(client, session):
    # 1. Setup player and package with quota = 1
    session.add(Player(steam_id="STEAM_P1", in_game_name="Player1"))
    session.add(Player(steam_id="STEAM_P2", in_game_name="Player2"))
    session.add(MembershipType(
        code="VIP_LIMITED",
        name="VIP Limitado",
        price_usd=25.0,
        billing_type="ONE_TIME",
        default_days=45,
        max_quota=1,
        is_active=True
    ))
    await session.commit()

    # 2. Add membership without days: should inherit default_days=45
    resp = await client.post("/api/v1/db/players/membership", json={
        "steam_id": "STEAM_P1",
        "membership_type": "VIP_LIMITED"
    })
    assert resp.status_code == 200

    # Verify duration
    m = (await session.exec(select(Membership).where(Membership.steam_id == "STEAM_P1"))).first()
    assert m is not None
    assert m.is_active is True
    assert m.end_time is not None
    delta = m.end_time - m.start_time
    assert delta.days in (44, 45) # depending on second precision

    # 3. Try to add for second player: should fail because quota is 1
    resp = await client.post("/api/v1/db/players/membership", json={
        "steam_id": "STEAM_P2",
        "membership_type": "VIP_LIMITED"
    })
    assert resp.status_code == 400
    assert "No hay cupos disponibles" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_multi_rcon_per_server_scoping(session, mocker):
    # 1. Setup two servers
    s1 = RconServer(name="Server Alpha", ip="10.0.0.1", port=7777, password="p1", scheme="http", is_active=True)
    s2 = RconServer(name="Server Beta", ip="10.0.0.2", port=7778, password="p2", scheme="http", is_active=True)
    session.add(s1)
    session.add(s2)
    session.add(Player(steam_id="STEAM_GLOBAL", in_game_name="Global VIP"))
    session.add(Player(steam_id="STEAM_ALPHA", in_game_name="Alpha Only VIP"))
    await session.commit()
    await session.refresh(s1)
    await session.refresh(s2)

    # 2. Add memberships: one global (server_id=None), one specific to s1 (server_id=s1.id)
    session.add(Membership(steam_id="STEAM_GLOBAL", membership_type="VIP_GLOBAL", is_active=True, server_id=None))
    session.add(Membership(steam_id="STEAM_ALPHA", membership_type="VIP_ALPHA", is_active=True, server_id=s1.id))
    await session.commit()

    # Mock RCON clients
    client1 = RCONClient(base_url=s1.base_url, password="p1")
    client2 = RCONClient(base_url=s2.base_url, password="p2")
    sync_mock1 = mocker.patch.object(client1, "sync_reserved_slots", return_value=None)
    sync_mock2 = mocker.patch.object(client2, "sync_reserved_slots", return_value=None)
    mocker.patch.object(client1, "sync_banned_slots", return_value=None)
    mocker.patch.object(client2, "sync_banned_slots", return_value=None)

    RCONManager.register_client(s1.base_url, "p1", client1)
    RCONManager.register_client(s2.base_url, "p2", client2)

    # Run sync_all_servers
    res = await RconServersService.sync_all_servers(session)
    assert res["ok"] is True

    # Server Alpha (s1) must have received BOTH STEAM_GLOBAL and STEAM_ALPHA
    synced_alpha = sync_mock1.call_args[0][0]
    assert "STEAM_GLOBAL" in synced_alpha
    assert "STEAM_ALPHA" in synced_alpha

    # Server Beta (s2) must ONLY have received STEAM_GLOBAL
    synced_beta = sync_mock2.call_args[0][0]
    assert "STEAM_GLOBAL" in synced_beta
    assert "STEAM_ALPHA" not in synced_beta
