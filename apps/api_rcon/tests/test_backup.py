import pytest
import pytest_asyncio
import time
import csv
from pathlib import Path
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient, ASGITransport
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from src.main import app
from src.connections.databases.db import get_session, Player, Membership, Role, PlayerRole, BotConfig
from src.security.guard import verify_api_key_guard
from src.config import ENVIRONMENT_SETTINGS
from src.modules.v1.services.backup_service import (
    create_database_sql_backup,
    generate_download_token,
    verify_download_token,
    get_available_backups,
    cleanup_old_backups,
    _escape_sql_value,
)
from src.modules.v1.services.export_service import (
    generate_memberships_csv,
    generate_export_download_token,
    verify_export_download_token,
)

sqlite_url = "sqlite+aiosqlite:///:memory:"
engine = create_async_engine(sqlite_url, connect_args={"check_same_thread": False}, poolclass=StaticPool)

global_session = None

async def get_session_override():
    global global_session
    yield global_session

def override_verify_api_key_guard():
    return "test-api-key"


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
    app.dependency_overrides[verify_api_key_guard] = lambda: "test-api-key"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


def test_sql_escape_value():
    assert _escape_sql_value(None) == "NULL"
    assert _escape_sql_value(True) == "TRUE"
    assert _escape_sql_value(False) == "FALSE"
    assert _escape_sql_value(42) == "42"
    assert _escape_sql_value("O'Reilly") == "'O''Reilly'"
    assert _escape_sql_value("Simple string") == "'Simple string'"


def test_download_token_verification():
    filename = "backup_20260922_000000.sql"
    token = generate_download_token(filename, expires_in_seconds=60)
    assert verify_download_token(filename, token) is True
    assert verify_download_token("other_file.sql", token) is False
    assert verify_download_token(filename, token + "tampered") is False

    expired_token = f"{int(time.time()) - 10}.fake_sig"
    assert verify_download_token(filename, expired_token) is False


def test_cleanup_old_backups(tmp_path: Path):
    import os
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    old_timestamp = time.time() - (30 * 86400)
    for i in range(15):
        file = backup_dir / f"backup_202501{i+1:02d}_000000.sql"
        file.write_text(f"DUMMY BACKUP {i}")
        file_time = old_timestamp + i * 100
        os.utime(file, (file_time, file_time))

    deleted = cleanup_old_backups(backup_dir=backup_dir, max_days=14, keep_min=10)
    assert deleted == 5
    remaining = sorted(list(backup_dir.glob("backup_*.sql")))
    assert len(remaining) == 10


@pytest.mark.asyncio
async def test_sql_backup_only_generation(session: AsyncSession, tmp_path: Path):
    # Setup Roles and Players
    role_fundador = Role(id=1546690312762564648, name="Fundador")
    session.add(role_fundador)

    p1 = Player(steam_id="76561198000000001", discord_id="discord_111", in_game_name="CapitanFundador")
    m1 = Membership(steam_id="76561198000000001", membership_type="VIP_COMUN", is_active=True)
    session.add(p1)
    session.add(m1)
    await session.commit()

    # Generate SQL backup - must ONLY generate SQL, not CSV
    sql_file = await create_database_sql_backup(session=session, backup_dir=tmp_path)

    assert sql_file.is_file()
    assert sql_file.suffix == ".sql"
    assert (tmp_path / "latest.sql").is_file()
    # Confirm no CSV is created by SQL backup routine
    assert not (tmp_path / "latest.csv").exists()
    assert len(list(tmp_path.glob("*.csv"))) == 0

    content = sql_file.read_text(encoding="utf-8")
    assert "BEGIN;" in content
    assert "COMMIT;" in content
    assert 'INSERT INTO "players"' in content
    assert "76561198000000001" in content


@pytest.mark.asyncio
async def test_on_demand_csv_export(session: AsyncSession, tmp_path: Path):
    role_fundador = Role(id=2, name="Fundador")
    session.add(role_fundador)

    p1 = Player(steam_id="76561198000000001", discord_id="discord_111", in_game_name="CapitanFundador")
    p2 = Player(steam_id="76561198000000002", discord_id=None, in_game_name="SoldadoRaso")
    session.add(p1)
    session.add(p2)
    await session.commit()

    t0 = datetime(2025, 1, 1, tzinfo=timezone.utc)
    t1 = datetime(2025, 3, 1, tzinfo=timezone.utc)

    m1 = Membership(steam_id="76561198000000001", membership_type="VIP_COMUN", start_time=t0, is_active=False)
    m2 = Membership(steam_id="76561198000000001", membership_type="VIP_EXPRESS", special_role_id=2, start_time=t1, is_active=True)
    m3 = Membership(steam_id="76561198000000002", membership_type="VIP_PERMANENTE", is_active=True)
    session.add_all([m1, m2, m3])
    await session.commit()

    # Generate on-demand CSV
    csv_file, filename, count = await generate_memberships_csv(session, export_dir=tmp_path)
    assert csv_file.is_file()
    assert count == 3
    assert filename.startswith("memberships_export_")
    assert filename.endswith(".csv")

    csv_content = csv_file.read_text(encoding="utf-8-sig")
    lines = list(csv.reader(csv_content.strip().splitlines()))
    headers = lines[0]
    assert headers == [
        "ID MEMBRESIA", "USUARIO", "ID DISCORD", "ID STEAM", "TIPO VIP",
        "ES BOOSTER", "ES FUNDADOR", "ROL VINCULADO", "ACTIVO", "FECHA INICIO",
        "FECHA FIN", "ESTADO RCON", "OBSERVACIONES"
    ]


@pytest.mark.asyncio
async def test_backup_and_export_api_endpoints(client: AsyncClient, session: AsyncSession, tmp_path: Path, monkeypatch):
    monkeypatch.setattr(ENVIRONMENT_SETTINGS.CONNECTIONS_SETTINGS, "BACKUP_DIR", str(tmp_path / "backups"))
    monkeypatch.setattr(ENVIRONMENT_SETTINGS.SECURITY_SETTINGS, "API_KEY", "test-secret-key")

    p = Player(steam_id="76561198000000002", discord_id="discord_222", in_game_name="Soldier")
    m = Membership(steam_id="76561198000000002", membership_type="VIP_EXPRESS")
    session.add(p)
    session.add(m)
    await session.commit()

    # 1. Create SQL backup via POST /api/v1/db/backup
    res_backup = await client.post("/api/v1/db/backup")
    assert res_backup.status_code == 200
    data_backup = res_backup.json()
    assert data_backup["ok"] is True
    assert data_backup["filename"].endswith(".sql")

    # 2. Create SQL backup via POST /api/v1/db/backups/create
    res_create = await client.post("/api/v1/db/backups/create")
    assert res_create.status_code == 200
    assert res_create.json()["ok"] is True
    assert res_create.json()["sql_file"].endswith(".sql")

    # 3. Generate download link for SQL
    res_link_sql = await client.post("/api/v1/db/backups/link", json={"format": "sql"})
    assert res_link_sql.status_code == 200
    link_data_sql = res_link_sql.json()
    assert link_data_sql["format"] == "sql"
    assert "token=" in link_data_sql["download_url"]

    # 4. Generate on-demand CSV via POST /api/v1/db/memberships/export
    res_export = await client.post("/api/v1/db/memberships/export")
    assert res_export.status_code == 200
    export_data = res_export.json()
    assert export_data["ok"] is True
    assert export_data["filename"].endswith(".csv")
    assert "token=" in export_data["download_url"]

    # 5. Download the exported CSV
    path_and_query = export_data["download_url"].split("/api/v1")[-1]
    res_csv_dl = await client.get(f"/api/v1{path_and_query}")
    assert res_csv_dl.status_code == 200
    assert "text/csv" in res_csv_dl.headers.get("content-type", "")
    assert "ID MEMBRESIA" in res_csv_dl.text

    # 6. Generate on-demand CSV via POST /api/v1/db/backups/link format=csv
    res_link_csv = await client.post("/api/v1/db/backups/link", json={"format": "csv"})
    assert res_link_csv.status_code == 200
    assert res_link_csv.json()["format"] == "csv"
    assert res_link_csv.json()["filename"].endswith(".csv")
