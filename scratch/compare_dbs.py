import asyncio, re
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

PROD_DB = "postgresql+asyncpg://u163006579_CgWGlvgFAC:Ahlz8ZR9qUpn3TqrI9RVgMUE@gamessao1079.bisecthosting.com:5432/s163006579_matefield_prod"

def parse_copy_block(sql_text, table_name):
    """Extract rows from a COPY block in a pg_dump file."""
    pattern = rf'COPY public\.{table_name}\s+\(([^)]+)\)\s+FROM stdin;\n(.*?)\n\\.'
    match = re.search(pattern, sql_text, re.DOTALL)
    if not match:
        return [], []
    cols = [c.strip() for c in match.group(1).split(',')]
    rows = []
    for line in match.group(2).strip().split('\n'):
        if line.strip():
            vals = line.split('\t')
            rows.append(dict(zip(cols, vals)))
    return cols, rows

async def main():
    # Read local backup
    with open('backup_wardogs.sql', 'r', encoding='utf-8') as f:
        local_sql = f.read()
    
    # Parse local backup
    _, local_players = parse_copy_block(local_sql, 'players')
    _, local_memberships = parse_copy_block(local_sql, 'memberships')
    _, local_roles = parse_copy_block(local_sql, 'roles')
    _, local_player_roles = parse_copy_block(local_sql, 'player_roles')
    
    local_linked = [p for p in local_players if p.get('discord_id', '\\N') != '\\N']
    
    print("=== LOCAL BACKUP (backup_wardogs.sql) ===")
    print(f"  Players total: {len(local_players)}")
    print(f"  Players linked (discord_id): {len(local_linked)}")
    print(f"  Memberships: {len(local_memberships)}")
    print(f"  Roles: {len(local_roles)}")
    print(f"  Player-Roles: {len(local_player_roles)}")
    print()
    
    # Read prod backup  
    with open('db_backup_prod.sql', 'r', encoding='utf-8') as f:
        prod_sql = f.read()
    
    _, prod_players = parse_copy_block(prod_sql, 'players')
    _, prod_memberships = parse_copy_block(prod_sql, 'memberships')
    _, prod_roles = parse_copy_block(prod_sql, 'roles')
    _, prod_player_roles = parse_copy_block(prod_sql, 'player_roles')
    
    prod_linked = [p for p in prod_players if p.get('discord_id', '\\N') != '\\N']
    
    print("=== PROD BACKUP (db_backup_prod.sql - del 15/sep) ===")
    print(f"  Players total: {len(prod_players)}")
    print(f"  Players linked (discord_id): {len(prod_linked)}")
    print(f"  Memberships: {len(prod_memberships)}")
    print(f"  Roles: {len(prod_roles)}")
    print(f"  Player-Roles: {len(prod_player_roles)}")
    print()
    
    # Now check LIVE prod
    engine = create_async_engine(PROD_DB)
    async with engine.begin() as conn:
        r = await conn.execute(text("SELECT count(*) FROM players"))
        p_count = r.scalar()
        r = await conn.execute(text("SELECT count(*) FROM players WHERE discord_id IS NOT NULL"))
        p_linked = r.scalar()
        r = await conn.execute(text("SELECT count(*) FROM memberships"))
        m_count = r.scalar()
        r = await conn.execute(text("SELECT count(*) FROM roles"))
        ro_count = r.scalar()
        r = await conn.execute(text("SELECT count(*) FROM player_roles"))
        pr_count = r.scalar()
    
    print("=== PROD LIVE (BisectHosting ahora mismo) ===")
    print(f"  Players total: {p_count}")
    print(f"  Players linked (discord_id): {p_linked}")
    print(f"  Memberships: {m_count}")
    print(f"  Roles: {ro_count}")
    print(f"  Player-Roles: {pr_count}")
    print()
    
    # Show linked players from local backup
    print("=== Vinculaciones en LOCAL BACKUP ===")
    for p in local_linked:
        print(f"  Steam: {p['steam_id']}  Discord: {p['discord_id']}  Obs: {p.get('observations','\\N')}")
    
    print()
    print("=== Vinculaciones en PROD BACKUP ===")
    for p in prod_linked:
        print(f"  Steam: {p['steam_id']}  Discord: {p['discord_id']}  Obs: {p.get('observations','\\N')}")

if __name__ == '__main__':
    asyncio.run(main())
