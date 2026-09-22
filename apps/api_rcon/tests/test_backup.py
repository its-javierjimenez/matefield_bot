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
    create_database_backup,
    generate_download_token,
    verify_download_token,
    get_available_backups,
    cleanup_old_backups
)

sqlite_url = "sqlite+aiosqlite:///test_backup.db"
engine = create_async_engine(sqlite_url, connect_args={"check_same_thread": False}, poolclass=StaticPool)

global_session = None

async def get_session_override():
    global global_session
    yield global_session

def override_verify_api_key_guard():
    return "test-api-key"

app.dependency_overrides[get_session] = get_session_override
app.dependency_overrides[verify_api_key_guard] = override_verify_api_key_guard


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
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_backup_service_generation(session: AsyncSession, tmp_path: Path):
    # Setup Roles (Fundador role)
    role_fundador = Role(id=1546690312762564648, name="Fundador")
    session.add(role_fundador)

    # 1. Linked Player with Fundador role
    p1 = Player(steam_id="76561198000000001", discord_id="discord_111", in_game_name="CapitanFundador")
    m1 = Membership(steam_id="76561198000000001", membership_type="VIP_COMUN", is_active=True)
    pr1 = PlayerRole(steam_id="76561198000000001", role_id=1546690312762564648)
    session.add(p1)
    session.add(m1)
    session.add(pr1)

    # 2. Linked Player without Fundador role
    p2 = Player(steam_id="76561198000000002", discord_id="discord_222", in_game_name="SoldadoComun")
    m2 = Membership(steam_id="76561198000000002", membership_type="VIP_EXPRESS", is_active=True)
    session.add(p2)
    session.add(m2)

    # 3. Unlinked Player (discord_id=None)
    p3 = Player(steam_id="76561198000000003", discord_id=None, in_game_name="FantasmaSinVincular")
    m3 = Membership(steam_id="76561198000000003", membership_type="VIP_PERMANENTE", is_active=True)
    session.add(p3)
    session.add(m3)

    cfg = BotConfig(config_key="BACKUP_TEST_KEY", config_value="tested_value")
    session.add(cfg)
    await session.commit()

    # Generate backup into temp directory
    sql_file, csv_file = await create_database_backup(session=session, backup_dir=tmp_path)

    # 1. Validate SQL file
    assert sql_file.is_file()
    sql_content = sql_file.read_text(encoding="utf-8")
    assert "BEGIN;" in sql_content
    assert "COMMIT;" in sql_content
    assert 'INSERT INTO "players"' in sql_content
    assert "76561198000000001" in sql_content
    assert "76561198000000002" in sql_content
    assert "76561198000000003" in sql_content

    # 2. Validate CSV file (Only linked players + Fundador status)
    assert csv_file.is_file()
    assert csv_file.suffix == ".csv"
    csv_content = csv_file.read_text(encoding="utf-8-sig")
    lines = list(csv.reader(csv_content.strip().splitlines()))
    headers = lines[0]
    assert headers == [
        "ID MEMBRESIA", "USUARIO", "ID DISCORD", "ID STEAM", "TIPO VIP",
        "ES FUNDADOR", "ACTIVO", "FECHA INICIO", "FECHA FIN", "ESTADO RCON", "OBSERVACIONES"
    ]

    rows = lines[1:]
    # Should only have 2 memberships (p1 and p2), p3 (unlinked) must be excluded
    assert len(rows) == 2

    row_p1 = next(r for r in rows if r[3] == "76561198000000001")
    assert row_p1[1] == "CapitanFundador"
    assert row_p1[2] == "discord_111"
    assert row_p1[4] == "VIP_COMUN"
    assert row_p1[5] == "SI"  # ES FUNDADOR

    row_p2 = next(r for r in rows if r[3] == "76561198000000002")
    assert row_p2[1] == "SoldadoComun"
    assert row_p2[2] == "discord_222"
    assert row_p2[4] == "VIP_EXPRESS"
    assert row_p2[5] == "NO"  # NOT FUNDADOR

    # Ensure unlinked player 3 is NOT in CSV
    assert not any(r[3] == "76561198000000003" for r in rows)

    # 3. Validate latest copies
    assert (tmp_path / "latest.sql").is_file()
    assert (tmp_path / "latest.csv").is_file()


def test_download_token_verification():
    filename = "backup_20260922_000000.csv"
    token = generate_download_token(filename, expires_in_seconds=60)
    assert verify_download_token(filename, token) is True

    # Token for different file fails
    assert verify_download_token("other_file.csv", token) is False

    # Tampered token fails
    assert verify_download_token(filename, token + "tampered") is False

    # Expired token fails
    expired_token = f"{int(time.time()) - 10}.fake_sig"
    assert verify_download_token(filename, expired_token) is False


@pytest.mark.asyncio
async def test_backup_api_endpoints(client: AsyncClient, session: AsyncSession, tmp_path: Path, monkeypatch):
    monkeypatch.setattr(ENVIRONMENT_SETTINGS.CONNECTIONS_SETTINGS, "BACKUP_DIR", str(tmp_path))
    monkeypatch.setattr(ENVIRONMENT_SETTINGS.SECURITY_SETTINGS, "API_KEY", "test-secret-key")

    # Seed data
    p = Player(steam_id="76561198000000002", discord_id="discord_222", in_game_name="Soldier")
    m = Membership(steam_id="76561198000000002", membership_type="VIP_EXPRESS")
    session.add(p)
    session.add(m)
    await session.commit()

    # 1. Create backup via POST /api/v1/db/backups/create
    res_create = await client.post("/api/v1/db/backups/create")
    assert res_create.status_code == 200
    data_create = res_create.json()
    assert data_create["ok"] is True
    assert "sql_file" in data_create
    assert "csv_file" in data_create
    assert data_create["csv_file"].endswith(".csv")

    # 2. List backups via GET /api/v1/db/backups
    res_list = await client.get("/api/v1/db/backups")
    assert res_list.status_code == 200
    backups = res_list.json()["backups"]
    assert len(backups) >= 2

    # 3. Generate download link for SQL
    res_link_sql = await client.post("/api/v1/db/backups/link", json={"format": "sql"})
    assert res_link_sql.status_code == 200
    link_data_sql = res_link_sql.json()
    assert link_data_sql["ok"] is True
    assert link_data_sql["format"] == "sql"
    download_url = link_data_sql["download_url"]
    assert "token=" in download_url

    # 4. Download SQL file via link
    path_and_query = download_url.split("/api/v1")[-1]
    res_download = await client.get(f"/api/v1{path_and_query}")
    assert res_download.status_code == 200
    assert "BEGIN;" in res_download.text
    assert "attachment" in res_download.headers.get("content-disposition", "")

    # 5. Generate download link for CSV
    res_link_csv = await client.post("/api/v1/db/backups/link", json={"format": "csv"})
    assert res_link_csv.status_code == 200
    csv_link_data = res_link_csv.json()
    assert csv_link_data["format"] == "csv"
    assert csv_link_data["filename"].endswith(".csv")
    csv_path_and_query = csv_link_data["download_url"].split("/api/v1")[-1]
    res_csv_download = await client.get(f"/api/v1{csv_path_and_query}")
    assert res_csv_download.status_code == 200
    assert "text/csv" in res_csv_download.headers.get("content-type", "")
    assert "ID MEMBRESIA" in res_csv_download.text

    # 6. Unauthorized download attempt
    res_unauth = await client.get(f"/api/v1/db/backups/download/{link_data_sql['filename']}")
    assert res_unauth.status_code == 403

    # 7. Authorized via API Key in query parameter
    res_auth_key = await client.get(
        f"/api/v1/db/backups/download/{link_data_sql['filename']}?api_key=test-secret-key"
    )
    assert res_auth_key.status_code == 200
