import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from src.main import app
from src.connections.databases.db import get_session
from src.security.guard import verify_api_key_guard
from src.connections.apis.rcon import RCONManager

TEST_SQLITE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(
        TEST_SQLITE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session(test_engine):
    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    async with AsyncSession(test_engine, expire_on_commit=False) as sess:
        yield sess

    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)


@pytest_asyncio.fixture
async def client(session):
    async def override_get_session():
        yield session

    def override_verify_guard():
        return True

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[verify_api_key_guard] = override_verify_guard

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.pop(get_session, None)
    app.dependency_overrides.pop(verify_api_key_guard, None)


@pytest.fixture(autouse=True)
def reset_rcon_pool():
    RCONManager.reset_pool()
    yield
    RCONManager.reset_pool()
