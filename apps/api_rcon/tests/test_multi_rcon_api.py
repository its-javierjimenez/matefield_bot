import pytest
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession
from wardogs_schemas import v1 as schemas

from src.connections.databases.db import RconServer
from src.connections.apis.rcon import RCONManager, RCONClient


@pytest.mark.asyncio
async def test_rcon_servers_crud_flow(client: AsyncClient, session: AsyncSession, mocker):
    dummy_status = schemas.Status(
        serverName="Servidor de Prueba Alpha",
        map="Desert_Valley",
        players=schemas.Players(current=12, max=64),
        matchSeconds=300
    )
    mocker.patch.object(RCONClient, "get_status", return_value=dummy_status)

    # 1. Initially empty
    list_resp = await client.get("/api/v1/rcon-servers?check_health=false")
    assert list_resp.status_code == 200
    assert list_resp.json() == []

    # 2. Create server without name (should auto-probe status)
    create_resp = await client.post("/api/v1/rcon-servers", json={
        "ip": "10.0.0.1",
        "port": 7777,
        "password": "pass",
        "scheme": "http",
        "is_active": True,
        "is_default": True
    })
    assert create_resp.status_code == 200
    created = create_resp.json()["server"]
    server_id = created["id"]
    assert created["name"] == "Servidor de Prueba Alpha"
    assert created["is_default"] is True

    # 3. Get server by ID
    get_resp = await client.get(f"/api/v1/rcon-servers/{server_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "Servidor de Prueba Alpha"

    # 4. Update server
    put_resp = await client.put(f"/api/v1/rcon-servers/{server_id}", json={
        "name": "Servidor Modificado",
        "port": 8888
    })
    assert put_resp.status_code == 200
    updated = put_resp.json()["server"]
    assert updated["name"] == "Servidor Modificado"
    assert updated["port"] == 8888

    # 5. Test server endpoint
    test_resp = await client.post(f"/api/v1/rcon-servers/{server_id}/test")
    assert test_resp.status_code == 200
    test_data = test_resp.json()
    assert test_data["is_online"] is True
    assert test_data["current_map"] == "Desert_Valley"
    assert test_data["player_count"] == 12

    # 6. Delete server
    del_resp = await client.delete(f"/api/v1/rcon-servers/{server_id}")
    assert del_resp.status_code == 200

    # 7. Confirm 404 after deletion
    del_get_resp = await client.get(f"/api/v1/rcon-servers/{server_id}")
    assert del_get_resp.status_code == 404


@pytest.mark.asyncio
async def test_rcon_servers_sync_all_endpoint(client: AsyncClient, session: AsyncSession, mocker):
    mocker.patch.object(RCONClient, "sync_reserved_slots", return_value=None)
    mocker.patch.object(RCONClient, "get_bans", return_value=[])
    mocker.patch.object(RCONClient, "sync_banned_slots", return_value=None)

    resp = await client.post("/api/v1/rcon-servers/sync-all")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert len(data["results"]) >= 1
    assert data["results"][0]["status"] == "SUCCESS"
