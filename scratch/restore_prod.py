import asyncio, re
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

PROD_DB = "postgresql+asyncpg://u163006579_CgWGlvgFAC:Ahlz8ZR9qUpn3TqrI9RVgMUE@gamessao1079.bisecthosting.com:5432/s163006579_matefield_prod"

def parse_ts(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace('+00', '+00:00'))
    except:
        return None

def parse_copy_block(sql_text, table_name):
    pattern = rf'COPY public\.{table_name}\s+\(([^)]+)\)\s+FROM stdin;\n(.*?)\n\\.'
    match = re.search(pattern, sql_text, re.DOTALL)
    if not match:
        return [], []
    cols = [c.strip() for c in match.group(1).split(',')]
    rows = []
    for line in match.group(2).strip().split('\n'):
        if line.strip():
            vals = line.split('\t')
            row = {}
            for i, c in enumerate(cols):
                v = vals[i] if i < len(vals) else '\\N'
                row[c] = None if v == '\\N' else v
            rows.append(row)
    return cols, rows

async def main():
    with open('db_backup_prod.sql', 'r', encoding='utf-8') as f:
        sql = f.read()

    parsed = {}
    for t in ['roles', 'players', 'memberships', 'player_roles']:
        cols, rows = parse_copy_block(sql, t)
        parsed[t] = (cols, rows)
        print(f"Parsed {t}: {len(rows)} rows")

    engine = create_async_engine(PROD_DB)
    async with engine.begin() as conn:
        print("\n--- TRUNCATE CASCADE ---")
        await conn.execute(text("TRUNCATE player_sessions, match_player_stats, match_team_stats, matches, bans, player_roles, memberships, players, roles, teams, bot_config, membership_type_configs CASCADE"))
        print("  OK")

        print("\n--- Roles ---")
        _, rows = parsed['roles']
        for r in rows:
            await conn.execute(text("INSERT INTO roles (id, name) VALUES (:id, :name)"), {"id": int(r['id']), "name": r['name']})
        print(f"  {len(rows)} insertados")

        print("\n--- Players ---")
        _, rows = parsed['players']
        for r in rows:
            await conn.execute(text(
                "INSERT INTO players (steam_id, discord_id, custom_welcome_message, observations, in_game_name, avatar_url) "
                "VALUES (:a, :b, :c, :d, :e, :f)"
            ), {"a": r['steam_id'], "b": r.get('discord_id'), "c": r.get('custom_welcome_message'), "d": r.get('observations'), "e": r.get('in_game_name'), "f": r.get('avatar_url')})
        print(f"  {len(rows)} insertados")

        print("\n--- Memberships ---")
        _, rows = parsed['memberships']
        for r in rows:
            rid = int(r['role_granted_id']) if r.get('role_granted_id') else None
            await conn.execute(text(
                "INSERT INTO memberships (id, steam_id, type, start_date, end_date, is_active, role_granted_id, rcon_sync_status) "
                "VALUES (:id, :sid, :tp, :sd, :ed, :ia, :rg, :rs)"
            ), {
                "id": int(r['id']),
                "sid": r['steam_id'],
                "tp": r['type'],
                "sd": parse_ts(r.get('start_date')),
                "ed": parse_ts(r.get('end_date')),
                "ia": r.get('is_active') == 't',
                "rg": rid,
                "rs": r.get('rcon_sync_status', 'PENDING'),
            })
        print(f"  {len(rows)} insertadas")

        print("\n--- Player-Roles ---")
        _, rows = parsed['player_roles']
        for r in rows:
            await conn.execute(text("INSERT INTO player_roles (steam_id, role_id) VALUES (:a, :b)"), {"a": r['steam_id'], "b": int(r['role_id'])})
        print(f"  {len(rows)} insertados")

        await conn.execute(text("SELECT setval('memberships_id_seq', (SELECT COALESCE(MAX(id),0) FROM memberships))"))
        await conn.execute(text("SELECT setval('roles_id_seq', (SELECT COALESCE(MAX(id),0) FROM roles))"))

    async with engine.begin() as conn:
        print(f"\n{'='*40}")
        print(f"  VERIFICACION FINAL PROD LIVE")
        print(f"{'='*40}")
        for label, q in [("Players", "SELECT count(*) FROM players"), ("Vinculados", "SELECT count(*) FROM players WHERE discord_id IS NOT NULL"), ("Memberships", "SELECT count(*) FROM memberships"), ("Roles", "SELECT count(*) FROM roles"), ("Player-Roles", "SELECT count(*) FROM player_roles")]:
            r = await conn.execute(text(q))
            print(f"  {label}: {r.scalar()}")
        r = await conn.execute(text("SELECT steam_id, discord_id, observations FROM players WHERE discord_id = '240644979393953792'"))
        row = r.fetchone()
        print(f"\n  >>> TU CUENTA: Steam={row[0]}, Discord={row[1]}, Obs={row[2]}")

if __name__ == '__main__':
    asyncio.run(main())
