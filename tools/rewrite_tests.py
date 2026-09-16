import re

files = ['apps/api_rcon/tests/test_sync.py', 'apps/api_rcon/tests/test_crud.py']

for file in files:
    with open(file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Imports
    content = content.replace("from sqlmodel import SQLModel, Session, create_engine", "from sqlmodel import SQLModel, Session\nfrom sqlmodel.ext.asyncio.session import AsyncSession\nfrom sqlalchemy.ext.asyncio import create_async_engine")
    
    # Engine
    content = content.replace('sqlite_url = "sqlite:///:memory:"', 'sqlite_url = "sqlite+aiosqlite:///:memory:"')
    content = content.replace('engine = create_engine(', 'engine = create_async_engine(')
    
    # Session override
    content = content.replace('def get_session_override():\n    with Session(engine) as session:\n        yield session', 'async def get_session_override():\n    async with AsyncSession(engine) as session:\n        yield session')
    
    # async fixture
    content = content.replace('@pytest.fixture(name="session")\ndef session_fixture():\n    SQLModel.metadata.create_all(engine)', '@pytest.fixture(name="session")\nasync def session_fixture():\n    async with engine.begin() as conn:\n        await conn.run_sync(SQLModel.metadata.create_all)')
    content = content.replace('    with Session(engine) as session:\n        yield session\n    SQLModel.metadata.drop_all(engine)', '    async with AsyncSession(engine) as session:\n        yield session\n    async with engine.begin() as conn:\n        await conn.run_sync(SQLModel.metadata.drop_all)')
    
    # client fixture
    content = content.replace('def client_fixture(session: Session):', 'async def client_fixture(session: AsyncSession):')
    
    # Test signatures
    content = re.sub(r'def test_(\w+)\(([^)]+)session: Session([^)]*)\):', r'async def test_\1(\2session: AsyncSession\3):', content)
    
    # DB calls inside tests
    content = re.sub(r'session\.commit\(', r'await session.commit(', content)
    content = re.sub(r'session\.refresh\(', r'await session.refresh(', content)
    content = re.sub(r'session\.exec\(', r'await session.exec(', content)
    content = re.sub(r'session\.get\(', r'await session.get(', content)
    content = re.sub(r'session\.delete\(', r'await session.delete(', content)

    # httpx AsyncClient
    content = content.replace("from fastapi.testclient import TestClient", "from httpx import AsyncClient, ASGITransport")
    content = content.replace("return TestClient(app)", "return AsyncClient(transport=ASGITransport(app=app), base_url='http://test')")
    content = content.replace("client: TestClient", "client: AsyncClient")
    content = re.sub(r'client\.(post|get|put|delete)\(', r'await client.\1(', content)

    with open(file, 'w', encoding='utf-8') as f:
        f.write(content)
