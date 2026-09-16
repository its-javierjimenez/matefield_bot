import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

DEV_DB = "postgresql+asyncpg://u163006579_K9hF1DxFjM:vBZLroJdlUBLSDWZvByeWP4n@gamessao1079.bisecthosting.com:5432/s163006579_matefield_dev"
# The DB from .env (which might be the real one)
LOCAL_DB = "postgresql+asyncpg://postgres:password@127.0.0.1:5432/wardogs"

async def check(name, url):
    try:
        engine = create_async_engine(url)
        async with engine.begin() as conn:
            res = await conn.execute(text("SELECT count(*) FROM memberships"))
            c = res.scalar()
            res2 = await conn.execute(text("SELECT count(*) FROM players WHERE discord_id IS NOT NULL"))
            c2 = res2.scalar()
            print(f"[{name}] Memberships: {c}, Linked players: {c2}")
    except Exception as e:
        print(f"[{name}] Error: {e}")

async def main():
    await check("DEV", DEV_DB)
    await check("LOCAL", LOCAL_DB)

if __name__ == '__main__':
    asyncio.run(main())
