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
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from src.config import ENVIRONMENT_SETTINGS

logger = logging.getLogger(__name__)


def get_backup_dir(base_dir: Optional[Path | str] = None) -> Path:
    """Returns the resolved backup directory and ensures it exists."""
    if base_dir:
        path = Path(base_dir)
    else:
        path = Path(ENVIRONMENT_SETTINGS.CONNECTIONS_SETTINGS.BACKUP_DIR)
    
    if not path.is_absolute():
        # Keep relative paths predictable relative to the current working directory
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
    # String or other representation
    val_str = str(val).replace("'", "''")
    return f"'{val_str}'"


async def create_database_backup(
    session: AsyncSession,
    backup_dir: Optional[Path | str] = None
) -> Tuple[Path, Path]:
    """
    Dumps the database into two files in backup_dir:
    1. A system-compatible SQL dump file (backup_<timestamp>.sql).
    2. An exterior-compatible CSV ZIP archive (backup_<timestamp>_csv.zip).
    Also updates latest.sql and latest_csv.zip convenience copies.
    """
    target_dir = get_backup_dir(backup_dir)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    sql_file = target_dir / f"backup_{timestamp}.sql"
    csv_zip_file = target_dir / f"backup_{timestamp}_csv.zip"

    sorted_tables = SQLModel.metadata.sorted_tables
    
    # 1. Generate SQL Backup
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
        pass  # alembic_version may not exist in test environments

    csv_data_map: Dict[str, str] = {}

    for table in sorted_tables:
        table_name = table.name
        columns = [c.name for c in table.columns]
        
        # Query rows for this table using SQLAlchemy select on table via connection
        query = sa_select(table)
        result = (await conn.execute(query)).fetchall()
        
        # --- SQL Output for table ---
        sql_lines.append(f"-- Table: {table_name}")
        if result:
            cols_quoted = ", ".join([f'"{col}"' for col in columns])
            for row in result:
                row_map = row._mapping
                values = [row_map.get(col) for col in columns]
                vals_escaped = ", ".join([_escape_sql_value(v) for v in values])
                sql_lines.append(f"INSERT INTO \"{table_name}\" ({cols_quoted}) VALUES ({vals_escaped});")
        sql_lines.append("")

        # --- CSV Output for table ---
        csv_buf = io.StringIO()
        csv_writer = csv.writer(csv_buf)
        csv_writer.writerow(columns)
        for row in result:
            row_map = row._mapping
            values = [row_map.get(col) for col in columns]

            formatted_vals = []
            for v in values:
                if v is None:
                    formatted_vals.append("")
                elif isinstance(v, datetime):
                    formatted_vals.append(v.isoformat())
                else:
                    formatted_vals.append(str(v))
            csv_writer.writerow(formatted_vals)
        
        csv_data_map[f"{table_name}.csv"] = csv_buf.getvalue()

    sql_lines.append("COMMIT;")
    sql_lines.append("")

    # Write SQL dump
    sql_file.write_text("\n".join(sql_lines), encoding="utf-8")

    # Write CSV ZIP
    with zipfile.ZipFile(csv_zip_file, mode="w", compression=zipfile.ZIP_DEFLATED) as zipf:
        for fname, content in csv_data_map.items():
            zipf.writestr(fname, content)

    # Convenience copies
    latest_sql = target_dir / "latest.sql"
    latest_csv = target_dir / "latest_csv.zip"
    try:
        shutil.copyfile(sql_file, latest_sql)
        shutil.copyfile(csv_zip_file, latest_csv)
    except Exception as e:
        logger.warning(f"Could not update latest backup copies: {e}")

    # Enforce retention policy
    cleanup_old_backups(
        target_dir,
        max_days=ENVIRONMENT_SETTINGS.CONNECTIONS_SETTINGS.BACKUP_RETENTION_DAYS,
        keep_min=10
    )

    logger.info(f"[Backup] Successfully generated backups: {sql_file.name}, {csv_zip_file.name}")
    return sql_file, csv_zip_file


def get_available_backups(backup_dir: Optional[Path | str] = None) -> List[Dict[str, Any]]:
    """Lists all available backup files sorted from newest to oldest."""
    target_dir = get_backup_dir(backup_dir)
    backups: List[Dict[str, Any]] = []
    
    for item in target_dir.iterdir():
        if not item.is_file():
            continue
        # Only return timestamped or latest backups
        if item.name.endswith(".sql"):
            fmt = "sql"
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
            "is_latest": item.name in ("latest.sql", "latest_csv.zip")
        })

    # Sort descending by creation date (non-latest first, or newest st_mtime)
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

    for pattern in ("backup_*.sql", "backup_*_csv.zip"):
        files = sorted(backup_dir.glob(pattern), key=lambda p: p.stat().st_mtime)
        # If we have more than keep_min, consider deleting those past cutoff
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
