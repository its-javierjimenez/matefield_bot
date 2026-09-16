import asyncio
import asyncpg

PROD_DB = "postgresql://u163006579_CgWGlvgFAC:Ahlz8ZR9qUpn3TqrI9RVgMUE@gamessao1079.bisecthosting.com:5432/s163006579_matefield_prod"

async def main():
    conn = await asyncpg.connect(PROD_DB)
    
    # Check players with discord_id linked that also have active memberships
    linked = await conn.fetch("""
        SELECT p.steam_id, p.discord_id, m.type, m.end_date, m.is_active
        FROM players p
        JOIN memberships m ON m.steam_id = p.steam_id
        WHERE p.discord_id IS NOT NULL AND m.is_active = true
        ORDER BY m.end_date ASC NULLS LAST
        LIMIT 30
    """)
    print(f"=== LINKED PLAYERS WITH ACTIVE MEMBERSHIPS ({len(linked)}) ===")
    for r in linked:
        print(dict(r))
    
    # How many players have discord_id?
    total_linked = await conn.fetchval("SELECT COUNT(*) FROM players WHERE discord_id IS NOT NULL")
    total_players = await conn.fetchval("SELECT COUNT(*) FROM players")
    print(f"\nTotal players: {total_players}, Linked: {total_linked}")
    
    await conn.close()

asyncio.run(main())
