import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlmodel import SQLModel, Session, select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from datetime import datetime, timezone, timedelta

from src.main import app
from src.connections.databases.db import get_session, Player, Membership, BotConfig, Role, PlayerRole
from src.security.guard import verify_api_key_guard
from sqlalchemy.pool import StaticPool
import src.modules.v1.router as router_module
from wardogs_schemas import v1 as schemas

sqlite_url = "sqlite+aiosqlite:///:memory:"
engine = create_async_engine(sqlite_url, connect_args={"check_same_thread": False}, poolclass=StaticPool)


global_session = None
async def get_session_override():
    global global_session
    yield global_session

def override_verify_api_key_guard():
    return True

@pytest_asyncio.fixture(name="session")
async def session_fixture():
    global global_session
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        global_session = session
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)

@pytest_asyncio.fixture(name="client")
async def client_fixture(session: AsyncSession):
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[verify_api_key_guard] = lambda: True
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        yield client

@pytest.mark.asyncio
async def test_edit_membership(client: AsyncClient, session: AsyncSession):
    now = datetime.now(timezone.utc)
    p = Player(steam_id="123")
    m = Membership(
        steam_id="123", 
        membership_type="VIP_EXPRESS", 
        is_active=True, 
        start_time=now - timedelta(days=2),
        end_time=now + timedelta(days=5)
    )
    session.add(p)
    session.add(m)
    await session.commit()
    
    response = await client.put(f"/api/v1/db/memberships/{m.id}", json={
        "days": 10,
        "membership_type": "VIP_PREMIUM",
        "is_active": False
    })
    
    assert response.status_code == 200
    await session.refresh(m)
    assert m.membership_type == "VIP_PREMIUM"
    assert m.is_active is False
    assert m.end_time is not None
    assert (m.end_time - m.start_time).days == 10

@pytest.mark.asyncio
async def test_delete_membership(client: AsyncClient, session: AsyncSession):
    p = Player(steam_id="123")
    m = Membership(steam_id="123", membership_type="VIP_EXPRESS", is_active=True, start_time=datetime.now(timezone.utc))
    session.add(p)
    session.add(m)
    await session.commit()
    
    m_id = m.id
    response = await client.delete(f"/api/v1/db/memberships/{m_id}")
    
    assert response.status_code == 200
    
    from sqlmodel import select
    deleted_m = (await session.exec(select(Membership).where(Membership.id == m_id))).first()
    assert deleted_m is None

@pytest.mark.asyncio
async def test_remove_special_role(client: AsyncClient, session: AsyncSession):
    p = Player(steam_id="123")
    r = Role(id="111222333", name="111222333")
    session.add(p)
    session.add(r)
    await session.commit()
    assert r.id is not None
    pr = PlayerRole(steam_id="123", role_id=r.id)
    session.add(pr)
    await session.commit()
    
    response = await client.delete(f"/api/v1/db/players/123/roles/111222333")
    assert response.status_code == 200
    
    deleted_pr = (await session.exec(select(PlayerRole).where(PlayerRole.steam_id == "123", PlayerRole.role_id == r.id))).first()
    assert deleted_pr is None

@pytest.mark.asyncio
async def test_edit_player(client: AsyncClient, session: AsyncSession):
    p = Player(steam_id="123", discord_id="456", custom_welcome_message="Hola")
    session.add(p)
    await session.commit()
    
    response = await client.put(f"/api/v1/db/players/123", json={
        "discord_id": "789",
        "custom_welcome_message": "Adios"
    })
    assert response.status_code == 200
    
    await session.refresh(p)
    assert p.discord_id == "789"
    assert p.custom_welcome_message == "Adios"

@pytest.mark.asyncio
async def test_edit_membership_auto_adjusts_date(client: AsyncClient, session: AsyncSession):
    now = datetime.now(timezone.utc)
    p = Player(steam_id="steam_edit_test", discord_id="discord_edit_test")
    m = Membership(
        steam_id="steam_edit_test",
        membership_type="VIP_COMUN",
        is_active=True,
        start_time=now - timedelta(days=2),
        end_time=now + timedelta(days=28)
    )
    session.add(p)
    session.add(m)
    await session.commit()

    # 1. Edit to VIP_PERMANENTE without explicit days -> end_time becomes None
    res1 = await client.put(f"/api/v1/db/memberships/{m.id}", json={"membership_type": "VIP_PERMANENTE"})
    assert res1.status_code == 200
    await session.refresh(m)
    assert m.membership_type == "VIP_PERMANENTE"
    assert m.end_time is None
    assert m.is_active is True

    # 2. Edit to VIP_EXPRESS without explicit days -> end_time shrinks to start_time + 15 days
    res2 = await client.put(f"/api/v1/db/memberships/{m.id}", json={"membership_type": "VIP_EXPRESS"})
    assert res2.status_code == 200
    await session.refresh(m)
    assert m.membership_type == "VIP_EXPRESS"
    assert m.end_time is not None
    assert (m.end_time - m.start_time).days == 15

@pytest.mark.asyncio
async def test_get_paginated_memberships_filter_discord_id(client: AsyncClient, session: AsyncSession):
    now = datetime.now(timezone.utc)
    p1 = Player(steam_id="steam_filter_1", discord_id="discord_filter_1")
    p2 = Player(steam_id="steam_filter_2", discord_id="discord_filter_2")
    m1 = Membership(
        steam_id="steam_filter_1",
        membership_type="VIP_COMUN",
        is_active=True,
        start_time=now,
        rcon_sync_status="SUCCESS"
    )
    m2 = Membership(
        steam_id="steam_filter_2",
        membership_type="VIP_EXPRESS",
        is_active=False,
        start_time=now,
        rcon_sync_status="PENDING"
    )
    session.add_all([p1, p2, m1, m2])
    await session.commit()

    # Query memberships for discord_filter_1
    res = await client.get("/api/v1/db/memberships?discord_id=discord_filter_1")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    item = data["memberships"][0]
    assert item["id"] == m1.id
    assert item["steam_id"] == "steam_filter_1"
    assert item["type"] == "VIP_COMUN"
    assert item["is_active"] is True
    assert item["rcon_sync_status"] == "SUCCESS"
    assert "start_date" in item
    assert "end_date" in item
    assert "special_role_id" in item









