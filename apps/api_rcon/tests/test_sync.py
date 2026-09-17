import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlmodel import SQLModel, Session
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from datetime import datetime, timezone, timedelta

from src.main import app
from src.connections.databases.db import get_session, Player, Membership, BotConfig, Role
from src.security.guard import verify_api_key_guard
from sqlalchemy.pool import StaticPool
import src.modules.v1.router as router_module
from wardogs_schemas import v1 as schemas

sqlite_url = "sqlite+aiosqlite:///test_sync.db"
engine = create_async_engine(sqlite_url, connect_args={"check_same_thread": False}, poolclass=StaticPool)

async def get_session_override():
    async with AsyncSession(engine) as session:
        yield session

def override_verify_api_key_guard():
    return True

app.dependency_overrides[get_session] = get_session_override
app.dependency_overrides[verify_api_key_guard] = override_verify_api_key_guard

@pytest_asyncio.fixture(name="session")
async def session_fixture():
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    async with AsyncSession(engine) as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)

@pytest_asyncio.fixture(name="client")
async def client_fixture(session: AsyncSession):
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        yield client

@pytest.fixture(autouse=True)
def mock_rcon(mocker):
    # Mock the RCON client functions used in the endpoint
    mocker.patch.object(router_module.rcon, 'get_reserved_slots', return_value=schemas.ReservedSlots(reservedSlots=[]))
    mocker.patch.object(router_module.rcon, 'sync_reserved_slots', return_value=None)

@pytest.mark.asyncio
async def test_sync_expires_old_memberships(client: AsyncClient, session: AsyncSession):
    now = datetime.now(timezone.utc)
    p = Player(steam_id="123", discord_id="456")
    m = Membership(
        steam_id="123", 
        membership_type="VIP_EXPRESS", 
        is_active=True, 
        start_time=now - timedelta(days=2),
        end_time=now - timedelta(days=1)
    )
    session.add(p)
    session.add(m)
    await session.commit()
    
    response = await client.post("/api/v1/db/sync_memberships")
    assert response.status_code == 200
    
    await session.refresh(m)
    assert m.is_active is False
    
    data = response.json()
    assert data["sync_data"] == [{"discord_id": "456", "active_memberships": [], "special_roles": []}]

@pytest.mark.asyncio
async def test_sync_adds_authorized_slots(client: AsyncClient, session: AsyncSession, mocker):
    mock_add = mocker.patch.object(router_module.rcon, 'sync_reserved_slots')
    
    now = datetime.now(timezone.utc)
    p = Player(steam_id="VALID_STEAM_ID", discord_id="456")
    m = Membership(
        steam_id="VALID_STEAM_ID", 
        membership_type="VIP_EXPRESS", 
        is_active=True, 
        start_time=now - timedelta(days=2),
        end_time=now + timedelta(days=1)
    )
    session.add(p)
    session.add(m)
    await session.commit()
    
    response = await client.post("/api/v1/db/sync_memberships")
    assert response.status_code == 200
    
    # RCON add/remove are currently paused (pass), so mock should NOT be called
    mock_add.assert_called_once()

@pytest.mark.asyncio
async def test_sync_removes_unauthorized_slots(client: AsyncClient, session: AsyncSession, mocker):
    mocker.patch.object(router_module.rcon, 'get_reserved_slots', 
                        return_value=schemas.ReservedSlots(reservedSlots=["UNAUTHORIZED_STEAM"]))
    mock_remove = mocker.patch.object(router_module.rcon, 'sync_reserved_slots')
    
    response = await client.post("/api/v1/db/sync_memberships")
    assert response.status_code == 200
    
    # RCON add/remove are currently paused (pass), so mock should NOT be called
    mock_remove.assert_called_once()

@pytest.mark.asyncio
async def test_sync_returns_discord_mappings(client: AsyncClient, session: AsyncSession):
    role = Role(code="VIP_EXPRESS", name="VIP Express", role_type="VIP", discord_role_id="999888777")
    session.add(role)
    await session.commit()
    
    response = await client.post("/api/v1/db/sync_memberships")
    assert response.status_code == 200
    
    data = response.json()
    assert "role_maps" in data
    assert data["role_maps"]["VIP_EXPRESS"] == 999888777

@pytest.mark.asyncio
async def test_sync_permanent_memberships(client: AsyncClient, session: AsyncSession, mocker):
    mock_add = mocker.patch.object(router_module.rcon, 'sync_reserved_slots')
    
    now = datetime.now(timezone.utc)
    p = Player(steam_id="PERM_STEAM_ID", discord_id="456")
    m = Membership(
        steam_id="PERM_STEAM_ID", 
        membership_type="VIP_FUNDADOR", 
        is_active=True, 
        start_time=now - timedelta(days=2),
        end_time=None
    )
    session.add(p)
    session.add(m)
    await session.commit()
    
    response = await client.post("/api/v1/db/sync_memberships")
    assert response.status_code == 200
    
    await session.refresh(m)
    assert m.is_active is True  # Permanent memberships do not expire
    # RCON add/remove are currently paused (pass), so mock should NOT be called
    mock_add.assert_called_once()


@pytest.mark.asyncio
async def test_sync_keeps_active_membership_in_sync_data(client: AsyncClient, session: AsyncSession):
    """
    Escenario real: Un jugador ya tiene VIP en Discord y se le crea una membresía activa.
    La API debe devolver su membership_type en active_memberships, lo que significa
    que el bot NO le quitará el rol (solo quita roles si active_memberships está vacío).
    """
    now = datetime.now(timezone.utc)
    p = Player(steam_id="EXISTING_VIP_STEAM", discord_id="111222333")
    m = Membership(
        steam_id="EXISTING_VIP_STEAM",
        membership_type="VIP_EXPRESS",
        is_active=True,
        start_time=now - timedelta(days=5),
        end_time=now + timedelta(days=25)  # Aún vigente
    )
    role = Role(code="VIP_EXPRESS", name="VIP Express", role_type="VIP", discord_role_id="999888777")
    session.add(p)
    session.add(m)
    session.add(role)
    await session.commit()

    response = await client.post("/api/v1/db/sync_memberships")
    assert response.status_code == 200

    data = response.json()
    # Buscar al jugador en sync_data
    user_entry = next((u for u in data["sync_data"] if u["discord_id"] == "111222333"), None)
    assert user_entry is not None
    # Debe tener VIP_EXPRESS como membresía activa → el bot le MANTIENE el rol
    assert "VIP_EXPRESS" in user_entry["active_memberships"]
    # El role_map debe existir para que el bot sepa qué rol corresponde
    assert data["role_maps"]["VIP_EXPRESS"] == 999888777


@pytest.mark.asyncio
async def test_sync_only_removes_role_when_all_memberships_expire(client: AsyncClient, session: AsyncSession):
    """
    Escenario: Un jugador tiene 2 membresías. Una expiró, pero la otra sigue activa.
    La API debe seguir reportando la activa → el bot NO quita el rol.
    """
    now = datetime.now(timezone.utc)
    p = Player(steam_id="MULTI_VIP_STEAM", discord_id="444555666")
    m_expired = Membership(
        steam_id="MULTI_VIP_STEAM",
        membership_type="VIP_MVP_GIFT",
        is_active=True,
        start_time=now - timedelta(days=10),
        end_time=now - timedelta(days=1)  # Expirada
    )
    m_active = Membership(
        steam_id="MULTI_VIP_STEAM",
        membership_type="VIP_EXPRESS",
        is_active=True,
        start_time=now - timedelta(days=2),
        end_time=now + timedelta(days=28)  # Vigente
    )
    config1 = BotConfig(config_key="ROLE_MAP_VIP_EXPRESS", config_value="999888777")
    config2 = BotConfig(config_key="ROLE_MAP_VIP_MVP_GIFT", config_value="111222333")
    session.add(p)
    session.add(m_expired)
    session.add(m_active)
    session.add(config1)
    session.add(config2)
    await session.commit()

    response = await client.post("/api/v1/db/sync_memberships")
    assert response.status_code == 200

    data = response.json()
    user_entry = next((u for u in data["sync_data"] if u["discord_id"] == "444555666"), None)
    assert user_entry is not None

    # La expirada fue desactivada por el sync
    await session.refresh(m_expired)
    assert m_expired.is_active is False

    # La activa sigue vigente
    await session.refresh(m_active)
    assert m_active.is_active is True

    # Solo VIP_EXPRESS debe aparecer como activa (VIP_MVP_GIFT expiró)
    assert "VIP_EXPRESS" in user_entry["active_memberships"]
    assert "VIP_MVP_GIFT" not in user_entry["active_memberships"]
    # → El bot le mantiene el rol 999888777 (VIP_EXPRESS) pero le quita el 111222333 (VIP_MVP_GIFT)
