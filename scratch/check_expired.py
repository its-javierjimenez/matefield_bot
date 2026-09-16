import asyncio
import asyncpg

PROD_DB = "postgresql://u163006579_CgWGlvgFAC:Ahlz8ZR9qUpn3TqrI9RVgMUE@gamessao1079.bisecthosting.com:5432/s163006579_matefield_prod"

async def main():
    conn = await asyncpg.connect(PROD_DB)
    
    # Check expired memberships
    expired = await conn.fetch("SELECT id, steam_id, type, end_date, is_active FROM memberships WHERE is_active = false")
    print(f"=== EXPIRED/INACTIVE MEMBERSHIPS ({len(expired)}) ===")
    for r in expired:
        print(dict(r))
    
    # Check MVP gifts
    mvp = await conn.fetch("SELECT id, steam_id, type, start_date, end_date, is_active FROM memberships WHERE type = 'VIP_MVP_GIFT'")
    print(f"\n=== MVP GIFT MEMBERSHIPS ({len(mvp)}) ===")
    for r in mvp:
        print(dict(r))
    
    await conn.close()

asyncio.run(main())
