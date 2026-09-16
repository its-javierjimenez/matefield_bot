import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

PROD_DB = "postgresql+asyncpg://u163006579_CgWGlvgFAC:Ahlz8ZR9qUpn3TqrI9RVgMUE@gamessao1079.bisecthosting.com:5432/s163006579_matefield_prod"

async def main():
    engine = create_async_engine(PROD_DB)
    async with engine.begin() as conn:
        r = await conn.execute(text("SELECT COUNT(*) FROM player_sessions"))
        print(f"Total sessions: {r.scalar()}")
        r2 = await conn.execute(text("SELECT steam_id, total_seconds, end_time FROM player_sessions ORDER BY start_time DESC LIMIT 5"))
        print("\n=== Recent Player Sessions ===")
        for row in r2.fetchall():
            print(f"  steam_id={row[0]}, total_seconds={row[1]}, end_time={row[2]}")

if __name__ == '__main__':
    asyncio.run(main())
