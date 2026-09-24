"""Script para clonar todos los datos de PRODUCCIÓN (PROD) a un entorno de destino (DEV o LOCAL).

Mantiene íntegras las relaciones, adapta los esquemas a la versión HEAD (DDD roles,
is_booster, payment_source, multi-rcon, membership_types) y preserva todos los
jugadores vinculados, membresías activas y estadísticas.
"""

import argparse
import asyncio
import logging
from typing import Any, Dict, List
from dotenv import dotenv_values
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("clone_prod")


async def fetch_table_rows(engine, table_name: str) -> List[Dict[str, Any]]:
    async with engine.connect() as conn:
        res = await conn.execute(text(f"SELECT * FROM {table_name};"))
        columns = res.keys()
        rows = [dict(zip(columns, row)) for row in res.fetchall()]
        logger.info(f"Leídos {len(rows)} registros de '{table_name}' en PROD")
        return rows


async def clone_data(target_name: str, target_url: str, prod_url: str):
    logger.info(f"=== INICIANDO CLONACIÓN DE PROD HACIA '{target_name.upper()}' ===")
    logger.info(f"Target URL: {target_url.split('@')[-1]}")

    prod_engine = create_async_engine(prod_url)
    target_engine = create_async_engine(target_url)

    # 1. Leer datos de PROD
    teams = await fetch_table_rows(prod_engine, "teams")
    roles_raw = await fetch_table_rows(prod_engine, "roles")
    players = await fetch_table_rows(prod_engine, "players")
    player_roles = await fetch_table_rows(prod_engine, "player_roles")
    memberships_raw = await fetch_table_rows(prod_engine, "memberships")
    bans = await fetch_table_rows(prod_engine, "bans")
    bot_config = await fetch_table_rows(prod_engine, "bot_config")
    membership_type_configs = await fetch_table_rows(prod_engine, "membership_type_configs")
    matches = await fetch_table_rows(prod_engine, "matches")
    match_team_stats = await fetch_table_rows(prod_engine, "match_team_stats")
    match_player_stats = await fetch_table_rows(prod_engine, "match_player_stats")
    player_sessions = await fetch_table_rows(prod_engine, "player_sessions")

    await prod_engine.dispose()

    # 2. Adaptar Roles al modelo DDD
    roles_adapted = []
    for r in roles_raw:
        role_id = r["id"]
        # En PROD id=1 tiene name='1546690312762564648'
        if role_id == 1:
            roles_adapted.append({
                "id": 1,
                "name": "Fundador Principal",
                "code": "OWNER_MAIN",
                "discord_role_id": r["name"],
                "role_type": "SYSTEM"
            })
        else:
            roles_adapted.append({
                "id": role_id,
                "name": r.get("name", f"Rol #{role_id}"),
                "code": r.get("code") or f"ROLE_{role_id}",
                "discord_role_id": r.get("discord_role_id") or r.get("name"),
                "role_type": r.get("role_type", "SPECIAL")
            })

    # 3. Adaptar Membresías
    memberships_adapted = []
    for m in memberships_raw:
        m_copy = dict(m)
        if "is_booster" not in m_copy or m_copy["is_booster"] is None:
            m_copy["is_booster"] = False
        if "payment_source" not in m_copy or not m_copy["payment_source"]:
            m_copy["payment_source"] = "MANUAL"
        if "server_id" not in m_copy:
            m_copy["server_id"] = None
        if "tebex_transaction_id" not in m_copy:
            m_copy["tebex_transaction_id"] = None
        if "tebex_subscription_id" not in m_copy:
            m_copy["tebex_subscription_id"] = None
        memberships_adapted.append(m_copy)

    # 4. Insertar en Target dentro de una sola transacción
    async with target_engine.begin() as conn:
        # Preservar in_game_name, avatar_url y configs locales si ya existían
        target_player_info = {}
        try:
            tp_res = await conn.execute(text("SELECT steam_id, in_game_name, avatar_url FROM players WHERE in_game_name IS NOT NULL OR avatar_url IS NOT NULL;"))
            for sid, ign, av in tp_res.fetchall():
                target_player_info[sid] = (ign, av)
        except Exception:
            pass

        target_custom_configs = {}
        try:
            t_configs = await conn.execute(text("SELECT config_key, config_value FROM bot_config;"))
            for k, v in t_configs.fetchall():
                if k in ("LINK_ROLE_ID", "BAN_ROLE_DEFAULT", "ANNOUNCEMENT_CHANNEL_ID") or k.startswith("BAN_ROLE_"):
                    target_custom_configs[k] = v
        except Exception:
            pass

        logger.info(f"Limpiando tablas existentes en {target_name}...")
        tables_to_truncate = [
            "match_player_stats", "match_team_stats", "player_sessions", "matches",
            "bans", "memberships", "player_roles", "membership_types", "rcon_servers",
            "roles", "players", "teams", "bot_config", "membership_type_configs"
        ]
        for t in tables_to_truncate:
            await conn.execute(text(f"TRUNCATE TABLE {t} CASCADE;"))

        # Insertar Teams
        if teams:
            logger.info(f"Insertando {len(teams)} teams...")
            await conn.execute(text("INSERT INTO teams (id, name, code) VALUES (:id, :name, :code)"), teams)

        # Insertar Roles adaptados
        if roles_adapted:
            logger.info(f"Insertando {len(roles_adapted)} roles adaptados...")
            await conn.execute(text(
                "INSERT INTO roles (id, name, code, discord_role_id, role_type) "
                "VALUES (:id, :name, :code, :discord_role_id, :role_type)"
            ), roles_adapted)
            await conn.execute(text("SELECT setval('roles_id_seq', (SELECT COALESCE(MAX(id), 1) FROM roles));"))

        # Insertar Players
        if players:
            logger.info(f"Insertando {len(players)} players...")
            for p in players:
                sid = p.get("steam_id")
                if sid in target_player_info:
                    cached_ign, cached_av = target_player_info[sid]
                    if not p.get("in_game_name") and cached_ign:
                        p["in_game_name"] = cached_ign
                    if not p.get("avatar_url") and cached_av:
                        p["avatar_url"] = cached_av
            await conn.execute(text(
                "INSERT INTO players (steam_id, discord_id, custom_welcome_message, observations, in_game_name, avatar_url) "
                "VALUES (:steam_id, :discord_id, :custom_welcome_message, :observations, :in_game_name, :avatar_url)"
            ), players)

        # Insertar RCON Servers (Semilla Servidor Principal)
        logger.info("Semillando servidor RCON principal...")
        await conn.execute(text(
            "INSERT INTO rcon_servers (id, name, ip, port, password, scheme, is_active, is_default) "
            "VALUES (1, 'Servidor Principal SAO', '169.155.127.77', 9001, 'dVt2ajQzYqGKnDft', 'http', true, true) "
            "ON CONFLICT (id) DO NOTHING;"
        ))
        await conn.execute(text("SELECT setval('rcon_servers_id_seq', (SELECT COALESCE(MAX(id), 1) FROM rcon_servers));"))

        # Insertar Membership Types estándar
        logger.info("Semillando membership_types...")
        vip_types = [
            {"code": "VIP_COMUN", "name": "VIP Común", "default_days": 30, "discord_role_id": "1546845168169259060", "is_active": True},
            {"code": "VIP_EXPRESS", "name": "VIP Express", "default_days": 15, "discord_role_id": "1546846355656417311", "is_active": True},
            {"code": "VIP_PERMANENTE", "name": "VIP Permanente", "default_days": 0, "discord_role_id": "1548089245195968572", "is_active": True},
            {"code": "VIP_SEED", "name": "VIP Seeder", "default_days": 3, "discord_role_id": "1546846355656417311", "is_active": True},
        ]
        await conn.execute(text(
            "INSERT INTO membership_types (code, name, default_days, discord_role_id, is_active) "
            "VALUES (:code, :name, :default_days, :discord_role_id, :is_active) "
            "ON CONFLICT (code) DO NOTHING;"
        ), vip_types)

        # Insertar Player Roles
        if player_roles:
            logger.info(f"Insertando {len(player_roles)} player_roles...")
            await conn.execute(text("INSERT INTO player_roles (steam_id, role_id) VALUES (:steam_id, :role_id)"), player_roles)

        # Insertar Memberships adaptadas
        if memberships_adapted:
            logger.info(f"Insertando {len(memberships_adapted)} memberships...")
            # En base de datos la columna es 'type', 'start_date', 'end_date', 'role_granted_id'
            await conn.execute(text(
                "INSERT INTO memberships ("
                "   id, steam_id, type, start_date, end_date, is_active, role_granted_id, "
                "   rcon_sync_status, is_booster, server_id, tebex_transaction_id, tebex_subscription_id, payment_source"
                ") VALUES ("
                "   :id, :steam_id, :type, :start_date, :end_date, :is_active, :role_granted_id, "
                "   :rcon_sync_status, :is_booster, :server_id, :tebex_transaction_id, :tebex_subscription_id, :payment_source"
                ")"
            ), memberships_adapted)
            await conn.execute(text("SELECT setval('memberships_id_seq', (SELECT COALESCE(MAX(id), 1) FROM memberships));"))

        # Insertar Bans
        if bans:
            logger.info(f"Insertando {len(bans)} bans...")
            await conn.execute(text(
                "INSERT INTO bans (id, steam_id, reason, is_active, rcon_sync_status, banned_at, expires_at) "
                "VALUES (:id, :steam_id, :reason, :is_active, :rcon_sync_status, :banned_at, :expires_at)"
            ), bans)
            await conn.execute(text("SELECT setval('bans_id_seq', (SELECT COALESCE(MAX(id), 1) FROM bans));"))

        # Insertar Bot Config
        merged_config = {r["config_key"]: r["config_value"] for r in bot_config} if bot_config else {}
        merged_config.update(target_custom_configs)
        if merged_config:
            logger.info(f"Insertando {len(merged_config)} bot_config...")
            config_rows = [{"config_key": k, "config_value": v} for k, v in merged_config.items()]
            await conn.execute(text("INSERT INTO bot_config (config_key, config_value) VALUES (:config_key, :config_value)"), config_rows)

        # Insertar Membership Type Configs
        if membership_type_configs:
            logger.info(f"Insertando {len(membership_type_configs)} membership_type_configs...")
            await conn.execute(text("INSERT INTO membership_type_configs (membership_type, max_quota) VALUES (:membership_type, :max_quota)"), membership_type_configs)

        # Insertar Matches
        if matches:
            logger.info(f"Insertando {len(matches)} matches...")
            await conn.execute(text(
                "INSERT INTO matches (id, map_name, start_time, end_time, winning_team_id) "
                "VALUES (:id, :map_name, :start_time, :end_time, :winning_team_id)"
            ), matches)

        # Insertar Match Team Stats
        if match_team_stats:
            logger.info(f"Insertando {len(match_team_stats)} match_team_stats...")
            await conn.execute(text(
                "INSERT INTO match_team_stats (match_id, team_id, score) "
                "VALUES (:match_id, :team_id, :score)"
            ), match_team_stats)

        # Insertar Match Player Stats (por lotes de 5000)
        if match_player_stats:
            logger.info(f"Insertando {len(match_player_stats)} match_player_stats en lotes...")
            chunk_size = 5000
            for i in range(0, len(match_player_stats), chunk_size):
                chunk = match_player_stats[i:i + chunk_size]
                await conn.execute(text(
                    "INSERT INTO match_player_stats (steam_id, match_id, team_id, kills, deaths, cash_earned) "
                    "VALUES (:steam_id, :match_id, :team_id, :kills, :deaths, :cash_earned)"
                ), chunk)

        # Insertar Player Sessions (por lotes de 5000)
        if player_sessions:
            logger.info(f"Insertando {len(player_sessions)} player_sessions en lotes...")
            chunk_size = 5000
            for i in range(0, len(player_sessions), chunk_size):
                chunk = player_sessions[i:i + chunk_size]
                await conn.execute(text(
                    "INSERT INTO player_sessions (id, steam_id, start_time, end_time, total_seconds, seeding_seconds) "
                    "VALUES (:id, :steam_id, :start_time, :end_time, :total_seconds, :seeding_seconds)"
                ), chunk)

        # Asegurar alembic_version en HEAD (i5e6a7b8c9d0)
        await conn.execute(text("DELETE FROM alembic_version;"))
        await conn.execute(text("INSERT INTO alembic_version (version_num) VALUES ('i5e6a7b8c9d0');"))

    await target_engine.dispose()
    logger.info(f"✅ ¡Clonación a '{target_name.upper()}' completada con éxito sin errores!")


async def main():
    parser = argparse.ArgumentParser(description="Clonar datos de PROD a DEV o LOCAL")
    parser.add_argument("--target", choices=["dev", "local", "both"], default="both", help="Destino de los datos")
    args = parser.parse_args()

    prod_env = dotenv_values(".env.prod")
    dev_env = dotenv_values(".env.dev")
    local_env = dotenv_values(".env.local")

    prod_url = prod_env.get("DATABASE_URL")
    dev_url = dev_env.get("DATABASE_URL")
    local_raw = local_env.get("DATABASE_URL")

    if not prod_url:
        raise ValueError("DATABASE_URL no encontrada en .env.prod")

    if args.target in ["dev", "both"]:
        if not dev_url:
            raise ValueError("DATABASE_URL no encontrada en .env.dev")
        await clone_data("dev", dev_url, prod_url)

    if args.target in ["local", "both"]:
        if not local_raw:
            raise ValueError("DATABASE_URL no encontrada en .env.local")
        local_url = local_raw.replace("@postgres:", "@127.0.0.1:")
        await clone_data("local", local_url, prod_url)


if __name__ == "__main__":
    asyncio.run(main())
