import asyncio
import asyncpg

PROD_DB = "postgresql://u163006579_CgWGlvgFAC:Ahlz8ZR9qUpn3TqrI9RVgMUE@gamessao1079.bisecthosting.com:5432/s163006579_matefield_prod"

async def main():
    conn = await asyncpg.connect(PROD_DB)
    
    # Check roles table
    roles = await conn.fetch("SELECT * FROM roles")
    print("=== ROLES TABLE ===")
    for r in roles:
        print(dict(r))
    
    # Check role_maps in bot_config
    configs = await conn.fetch("SELECT * FROM bot_config WHERE config_key LIKE 'ROLE_MAP_%'")
    print("\n=== ROLE_MAP CONFIGS ===")
    for c in configs:
        print(dict(c))
    
    # Check active memberships
    memberships = await conn.fetch("SELECT id, steam_id, type, start_date, end_date, is_active, role_granted_id FROM memberships WHERE is_active = true LIMIT 20")
    print(f"\n=== ACTIVE MEMBERSHIPS ({len(memberships)}) ===")
    for m in memberships:
        print(dict(m))

    # Check player_roles 
    player_roles = await conn.fetch("SELECT * FROM player_roles")
    print(f"\n=== PLAYER_ROLES ({len(player_roles)}) ===")
    for pr in player_roles:
        print(dict(pr))
    
    await conn.close()

asyncio.run(main())
