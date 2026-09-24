import csv
import hashlib
import hmac
import io
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple
from sqlmodel import select, col
from sqlmodel.ext.asyncio.session import AsyncSession

from src.config import ENVIRONMENT_SETTINGS
from src.connections.databases.db import Player, Membership, Role, PlayerRole

logger = logging.getLogger("wardogs.export")


def get_export_dir(base_dir: Optional[Path | str] = None) -> Path:
    """Returns the export directory, creating it if needed."""
    if base_dir:
        path = Path(base_dir)
    else:
        path = Path("data/exports")
    path.mkdir(parents=True, exist_ok=True)
    return path


from src.security.tokens import (
    generate_secure_download_token,
    verify_secure_download_token,
)

# Backwards-compatible aliases
generate_export_download_token = generate_secure_download_token
verify_export_download_token = verify_secure_download_token


async def generate_memberships_csv(
    session: AsyncSession,
    export_dir: Optional[Path | str] = None
) -> Tuple[Path, str, int]:
    """
    Generates an exterior-compatible CSV file containing all existing memberships
    and linked accounts with their roles, booster and founder status.
    Returns (file_path, filename, total_records).
    """
    target_dir = get_export_dir(export_dir)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"memberships_export_{timestamp}.csv"
    csv_file = target_dir / filename

    # Map roles
    roles = (await session.exec(select(Role))).all()
    role_map = {r.id: r.name for r in roles if r.id is not None}
    founder_role_ids = {
        r.id for r in roles
        if r.name and "fundador" in r.name.strip().lower()
    }

    # Find players with founder role registered in player_roles
    founder_steam_ids = set()
    if founder_role_ids:
        prs = (await session.exec(
            select(PlayerRole.steam_id).where(col(PlayerRole.role_id).in_(founder_role_ids))
        )).all()
        founder_steam_ids = set(prs)

    # Query all memberships with outer join to Player
    stmt = (
        select(Membership, Player)
        .outerjoin(Player, col(Membership.steam_id) == col(Player.steam_id))
        .order_by(col(Membership.is_active).desc(), col(Membership.id).desc())
    )
    results = (await session.exec(stmt)).all()

    # Track the earliest date the founder role was acquired via membership per player
    player_founder_start = {}
    for m, _ in results:
        s_id = str(m.steam_id)
        if m.special_role_id is not None and m.special_role_id in founder_role_ids:
            if m.start_time:
                curr = player_founder_start.get(s_id)
                if curr is None or m.start_time < curr:
                    player_founder_start[s_id] = m.start_time

    csv_headers = [
        "ID MEMBRESIA",
        "USUARIO",
        "ID DISCORD",
        "ID STEAM",
        "TIPO VIP",
        "ES BOOSTER",
        "ES FUNDADOR",
        "ROL VINCULADO",
        "ACTIVO",
        "FECHA INICIO",
        "FECHA FIN",
        "ESTADO RCON",
        "OBSERVACIONES"
    ]

    csv_buf = io.StringIO()
    csv_writer = csv.writer(csv_buf, lineterminator="\n")
    csv_writer.writerow(csv_headers)

    for m, p in results:
        steam_id = str(m.steam_id)
        discord_id = str(p.discord_id) if (p and p.discord_id) else "NO VINCULADO"
        user_name = p.in_game_name if (p and p.in_game_name) else ""
        vip_type = str(m.membership_type or "")
        sp_role_name = role_map.get(m.special_role_id, "") if m.special_role_id else ""

        is_founder = False
        if steam_id in founder_steam_ids or (m.special_role_id is not None and m.special_role_id in founder_role_ids):
            first_founder_date = player_founder_start.get(steam_id)
            if first_founder_date is not None:
                # Acquired founder via membership: valid from that purchase date onwards
                if m.start_time:
                    m_time = m.start_time if m.start_time.tzinfo else m.start_time.replace(tzinfo=timezone.utc)
                    f_time = first_founder_date if first_founder_date.tzinfo else first_founder_date.replace(tzinfo=timezone.utc)
                    is_founder = m_time >= f_time
                else:
                    is_founder = True
            else:
                # Directly linked founder role to player account
                is_founder = True

        csv_writer.writerow([
            m.id,
            user_name,
            discord_id,
            steam_id,
            vip_type,
            "SI" if m.is_booster else "NO",
            "SI" if is_founder else "NO",
            sp_role_name,
            "SI" if m.is_active else "NO",
            m.start_time.strftime("%Y-%m-%d %H:%M:%S") if m.start_time else "",
            m.end_time.strftime("%Y-%m-%d %H:%M:%S") if m.end_time else "PERMANENTE",
            m.rcon_sync_status or "",
            (p.observations or "") if p else ""
        ])

    csv_file.write_text(csv_buf.getvalue(), encoding="utf-8-sig")
    logger.info(f"[Export] Generated memberships CSV: {filename} with {len(results)} records")
    return csv_file, filename, len(results)
