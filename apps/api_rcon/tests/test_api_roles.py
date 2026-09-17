import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from src.main import app
from src.connections.databases.db import get_session, Player, Role, RoleType, PlayerRole

sqlite_url = "sqlite+aiosqlite:///test_roles.db"
engine = create_async_engine(sqlite_url, connect_args={"check_same_thread": False}, poolclass=StaticPool)

async def override_get_session():
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session

app.dependency_overrides[get_session] = override_get_session
from src.security.guard import verify_api_key_guard

def override_verify_api_key_guard():
    return True

app.dependency_overrides[verify_api_key_guard] = override_verify_api_key_guard


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)

@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

@pytest_asyncio.fixture
async def session():
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session

@pytest.mark.asyncio
async def test_get_player_active_role(client: AsyncClient, session: AsyncSession):
    # Arrange
    player = Player(steam_id="steam_admin", discord_id="discord_admin")
    role_admin = Role(code="SUPERADMIN", name="Super Admin", role_type=RoleType.SYSTEM)
    session.add(player)
    session.add(role_admin)
    await session.commit()
    
    player_role = PlayerRole(steam_id="steam_admin", role_id=role_admin.id)
    session.add(player_role)
    await session.commit()

    # Act
    response = await client.get("/api/v1/db/players/steam/steam_admin", headers={"Authorization": "Bearer local-api-key"})
    
    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["active_role"] == "ADMIN" # Fallback mapped logical role
    
@pytest.mark.asyncio
async def test_role_register_and_assign(client: AsyncClient, session: AsyncSession):
    # Test new role registration endpoint
    player = Player(steam_id="steam_test1")
    session.add(player)
    await session.commit()
    
    # Register Role
    reg_resp = await client.post("/api/v1/db/roles", json={
        "code": "TEST_VIP",
        "name": "Test VIP",
        "role_type": "VIP",
        "discord_role_id": "111222"
    }, headers={"Authorization": "Bearer local-api-key"})
    assert reg_resp.status_code == 200
    
    # Assign Role
    assign_resp = await client.post("/api/v1/db/players/steam_test1/roles/TEST_VIP", headers={"Authorization": "Bearer local-api-key"})
    assert assign_resp.status_code == 200
    
    # Verify Assignment
    get_resp = await client.get("/api/v1/db/players/steam/steam_test1", headers={"Authorization": "Bearer local-api-key"})
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["active_role"] == "VIP"
