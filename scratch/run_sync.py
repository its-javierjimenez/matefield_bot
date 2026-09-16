import asyncio
import aiohttp
import asyncpg

PROD_DB = "postgresql://u163006579_CgWGlvgFAC:Ahlz8ZR9qUpn3TqrI9RVgMUE@gamessao1079.bisecthosting.com:5432/s163006579_matefield_prod"
RCON_TOKEN = "dVt2ajQzYqGKnDft"

async def main():
    # 1. Fetch from RCON
    async with aiohttp.ClientSession(headers={"Authorization": f"Bearer {RCON_TOKEN}"}) as http_session:
        async with http_session.get("http://169.155.127.77:9001/v1/bans") as resp:
            data = await resp.json()
            rcon_bans = data.get("bans", [])
            rcon_steam_ids = set([b["steamId"] for b in rcon_bans if b.get("steamId")])
            print(f"RCON has {len(rcon_steam_ids)} bans.")

    # 2. Sync to DB using raw SQL
    conn = await asyncpg.connect(PROD_DB)
    
    # Get active bans from DB
    records = await conn.fetch("SELECT steam_id FROM bans WHERE is_active = true")
    db_steam_ids = set([r["steam_id"] for r in records])
    print(f"DB has {len(db_steam_ids)} active bans.")
    
    missing = rcon_steam_ids - db_steam_ids
    print(f"Missing in DB: {len(missing)}")
    
    for sid in missing:
        # Ensure player exists
        player_exists = await conn.fetchval("SELECT steam_id FROM players WHERE steam_id = $1", sid)
        if not player_exists:
            await conn.execute("INSERT INTO players (steam_id) VALUES ($1)", sid)
            
        # Insert ban
        await conn.execute("""
            INSERT INTO bans (steam_id, reason, is_active, rcon_sync_status, banned_at)
            VALUES ($1, $2, true, 'SUCCESS', NOW())
        """, sid, "Synced from RCON")
        
    await conn.close()
    print("Sync complete.")

if __name__ == "__main__":
    asyncio.run(main())
