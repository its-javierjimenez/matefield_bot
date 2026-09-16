import asyncio
import asyncpg

PROD_DB = "postgresql://u163006579_CgWGlvgFAC:Ahlz8ZR9qUpn3TqrI9RVgMUE@gamessao1079.bisecthosting.com:5432/s163006579_matefield_prod"

async def main():
    conn = await asyncpg.connect(PROD_DB)
    
    # Check: Are there players with NO active memberships but who are linked?
    # These are the ones whose roles should have been pruned
    no_active = await conn.fetch("""
        SELECT p.steam_id, p.discord_id
        FROM players p
        WHERE p.discord_id IS NOT NULL
        AND NOT EXISTS (
            SELECT 1 FROM memberships m 
            WHERE m.steam_id = p.steam_id AND m.is_active = true
        )
    """)
    print(f"=== LINKED PLAYERS WITH NO ACTIVE MEMBERSHIPS ({len(no_active)}) ===")
    for r in no_active:
        print(dict(r))
        
    # Check: players who have ONLY expired memberships (had VIP, lost it)
    lost_vip = await conn.fetch("""
        SELECT p.steam_id, p.discord_id, 
            (SELECT string_agg(m2.type, ', ') FROM memberships m2 WHERE m2.steam_id = p.steam_id AND m2.is_active = false) as expired_types
        FROM players p
        WHERE p.discord_id IS NOT NULL
        AND EXISTS (
            SELECT 1 FROM memberships m WHERE m.steam_id = p.steam_id AND m.is_active = false
        )
        AND NOT EXISTS (
            SELECT 1 FROM memberships m WHERE m.steam_id = p.steam_id AND m.is_active = true
        )
    """)
    print(f"\n=== LINKED PLAYERS WHO LOST ALL MEMBERSHIPS ({len(lost_vip)}) ===")
    for r in lost_vip:
        print(dict(r))
    
    await conn.close()

asyncio.run(main())
