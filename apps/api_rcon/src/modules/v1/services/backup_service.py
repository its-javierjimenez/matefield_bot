import os
import csv
import io
import time
import hmac
import hashlib
import shutil
import zipfile
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy import text, select as sa_select
from sqlmodel import SQLModel, select, col
from sqlmodel.ext.asyncio.session import AsyncSession

from src.config import ENVIRONMENT_SETTINGS
from src.connections.databases.db import Player, Membership, Role, PlayerRole

logger = logging.getLogger(__name__)


def get_backup_dir(base_dir: Optional[Path | str] = None) -> Path:
    """Returns the resolved backup directory and ensures it exists."""
    if base_dir:
        path = Path(base_dir)
    else:
        path = Path(ENVIRONMENT_SETTINGS.CONNECTIONS_SETTINGS.BACKUP_DIR)
    
    if not path.is_absolute():
        path = path.resolve()
    
    path.mkdir(parents=True, exist_ok=True)
    return path


def generate_download_token(filename: str, expires_in_seconds: int = 900) -> str:
    """Generates a stateless, tamper-proof HMAC-SHA256 download token."""
    expiry_timestamp = int(time.time()) + expires_in_seconds
    key = ENVIRONMENT_SETTINGS.SECURITY_SETTINGS.API_KEY.encode("utf-8")
    message = f"{filename}:{expiry_timestamp}".encode("utf-8")
    sig = hmac.new(key, message, hashlib.sha256).hexdigest()
    return f"{expiry_timestamp}.{sig}"


def verify_download_token(filename: str, token: str) -> bool:
    """Verifies that an HMAC download token is valid and unexpired."""
    try:
        parts = token.split(".", 1)
        if len(parts) != 2:
            return False
        expiry_timestamp_str, sig = parts
        expiry_timestamp = int(expiry_timestamp_str)
        if expiry_timestamp < int(time.time()):
            return False
        
        key = ENVIRONMENT_SETTINGS.SECURITY_SETTINGS.API_KEY.encode("utf-8")
        message = f"{filename}:{expiry_timestamp}".encode("utf-8")
        expected_sig = hmac.new(key, message, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected_sig, sig)
    except Exception as e:
        logger.warning(f"Error verifying download token: {e}")
        return False


def _escape_sql_value(val: Any) -> str:
    """Formats a Python value as a standard SQL literal."""
    if val is None:
        return "NULL"
    if isinstance(val, bool):
        return "TRUE" if val else "FALSE"
    if isinstance(val, (int, float)):
        return str(val)
    if isinstance(val, datetime):
        return f"'{val.isoformat()}'"
    val_str = str(val).replace("'", "''")
    return f"'{val_str}'"


async def create_database_backup(
    session: AsyncSession,
    backup_dir: Optional[Path | str] = None
) -> Tuple[Path, Path]:
    """
    Dumps the database into two files in backup_dir:
    1. A system-compatible SQL dump file (backup_<timestamp>.sql).
    2. An exterior-compatible CSV file (backup_<timestamp>.csv) containing
       only memberships of linked players and their 'Es Fundador' status.
    Also updates latest.sql and latest.csv convenience copies.
    """
    target_dir = get_backup_dir(backup_dir)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    sql_file = target_dir / f"backup_{timestamp}.sql"
    csv_file = target_dir / f"backup_{timestamp}.csv"

    sorted_tables = SQLModel.metadata.sorted_tables
    
    # 1. Generate Full SQL Backup (All tables)
    sql_lines: List[str] = [
        "-- --------------------------------------------------------",
        f"-- Matefield Database Backup",
        f"-- Generated at: {datetime.now(timezone.utc).isoformat()}",
        "-- --------------------------------------------------------",
        "BEGIN;",
        ""
    ]

    conn = await session.connection()

    # Handle alembic_version if exists
    try:
        alembic_res = (await conn.execute(text("SELECT version_num FROM alembic_version"))).fetchall()
        if alembic_res:
            sql_lines.append("-- Table: alembic_version")
            sql_lines.append("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL);")
            for row in alembic_res:
                v = row[0] if isinstance(row, (tuple, list)) else getattr(row, "version_num", str(row))
                sql_lines.append(f"INSERT INTO alembic_version (version_num) VALUES ({_escape_sql_value(v)});")
            sql_lines.append("")
    except Exception:
        pass

    for table in sorted_tables:
        table_name = table.name
        columns = [c.name for c in table.columns]
        
        query = sa_select(table)
        result = (await conn.execute(query)).fetchall()
        
        sql_lines.append(f"-- Table: {table_name}")
        if result:
            cols_quoted = ", ".join([f'"{col}"' for col in columns])
            for row in result:
                row_map = row._mapping
                values = [row_map.get(col) for col in columns]
                vals_escaped = ", ".join([_escape_sql_value(v) for v in values])
                sql_lines.append(f"INSERT INTO \"{table_name}\" ({cols_quoted}) VALUES ({vals_escaped});")
        sql_lines.append("")

    sql_lines.append("COMMIT;")
    sql_lines.append("")
    sql_file.write_text("\n".join(sql_lines), encoding="utf-8")

    # 2. Generate CSV Backup (Memberships of linked players + Fundador status)
    role_rows = (await session.exec(select(Role))).all()
    founder_role_ids = {
        r.id for r in role_rows
        if r.id == 1546690312762564648 or (r.name and "fundador" in r.name.lower())
    }

    founder_steam_ids = set()
    if founder_role_ids:
        pr_rows = (await session.exec(
            select(PlayerRole.steam_id).where(col(PlayerRole.role_id).in_(founder_role_ids))
        )).all()
        founder_steam_ids = set(pr_rows)

    # Query memberships with linked players
    stmt_memberships = (
        select(Membership, Player)
        .join(Player, col(Membership.steam_id) == col(Player.steam_id))
        .where(col(Player.discord_id).is_not(None))
        .where(col(Player.discord_id) != "")
        .order_by(col(Membership.is_active).desc(), col(Membership.id).desc())
    )
    membership_rows = (await session.exec(stmt_memberships)).all()

    csv_headers = [
        "ID MEMBRESIA",
        "USUARIO",
        "ID DISCORD",
        "ID STEAM",
        "TIPO VIP",
        "ES FUNDADOR",
        "ACTIVO",
        "FECHA INICIO",
        "FECHA FIN",
        "ESTADO RCON",
        "OBSERVACIONES"
    ]

    csv_buf = io.StringIO()
    csv_writer = csv.writer(csv_buf, lineterminator="\n")
    csv_writer.writerow(csv_headers)

    for m, p in membership_rows:
        s_id = str(p.steam_id)
        t_vip = str(m.membership_type or "")
        sp_id = m.special_role_id

        is_founder = (
            s_id in founder_steam_ids
            or ("fundador" in t_vip.lower())
            or (sp_id is not None and sp_id in founder_role_ids)
        )

        csv_writer.writerow([
            m.id,
            p.in_game_name or "",
            p.discord_id or "",
            s_id,
            t_vip,
            "SI" if is_founder else "NO",
            "SI" if m.is_active else "NO",
            m.start_time.strftime("%Y-%m-%d %H:%M:%S") if m.start_time else "",
            m.end_time.strftime("%Y-%m-%d %H:%M:%S") if m.end_time else "PERMANENTE",
            m.rcon_sync_status or "",
            p.observations or ""
        ])

    csv_file.write_text(csv_buf.getvalue(), encoding="utf-8-sig")

    # Convenience copies
    latest_sql = target_dir / "latest.sql"
    latest_csv = target_dir / "latest.csv"
    try:
        shutil.copyfile(sql_file, latest_sql)
        shutil.copyfile(csv_file, latest_csv)
    except Exception as e:
        logger.warning(f"Could not update latest backup copies: {e}")

    # Enforce retention policy
    cleanup_old_backups(
        target_dir,
        max_days=ENVIRONMENT_SETTINGS.CONNECTIONS_SETTINGS.BACKUP_RETENTION_DAYS,
        keep_min=10
    )

    logger.info(f"[Backup] Successfully generated backups: {sql_file.name}, {csv_file.name}")
    return sql_file, csv_file


def get_available_backups(backup_dir: Optional[Path | str] = None) -> List[Dict[str, Any]]:
    """Lists all available backup files sorted from newest to oldest."""
    target_dir = get_backup_dir(backup_dir)
    backups: List[Dict[str, Any]] = []
    
    for item in target_dir.iterdir():
        if not item.is_file():
            continue
        if item.name.endswith(".sql"):
            fmt = "sql"
        elif item.name.endswith(".csv"):
            fmt = "csv"
        elif item.name.endswith(".zip"):
            fmt = "csv"
        else:
            continue

        stat = item.stat()
        created_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
        backups.append({
            "filename": item.name,
            "format": fmt,
            "size_bytes": stat.st_size,
            "created_at": created_at,
            "is_latest": item.name in ("latest.sql", "latest.csv", "latest_csv.zip")
        })

    backups.sort(key=lambda x: x["created_at"], reverse=True)
    return backups


def cleanup_old_backups(
    backup_dir: Path,
    max_days: int = 14,
    keep_min: int = 10
) -> int:
    """Removes timestamped backups older than max_days while keeping at least keep_min."""
    deleted_count = 0
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=max_days)

    for pattern in ("backup_*.sql", "backup_*.csv", "backup_*_csv.zip"):
        files = sorted(backup_dir.glob(pattern), key=lambda p: p.stat().st_mtime)
        while len(files) > keep_min:
            oldest = files[0]
            mtime = datetime.fromtimestamp(oldest.stat().st_mtime, tz=timezone.utc)
            if mtime < cutoff:
                try:
                    oldest.unlink()
                    deleted_count += 1
                    files.pop(0)
                except Exception as e:
                    logger.warning(f"Could not delete old backup {oldest}: {e}")
                    break
            else:
                break

    return deleted_count
