import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
url = "postgresql+asyncpg://u163006579_K9hF1DxFjM:vBZLroJdlUBLSDWZvByeWP4n@gamessao1079.bisecthosting.com:5432/s163006579_matefield_dev"
async def main():
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        res = await conn.execute(text("SELECT count(*) FROM memberships"))
        c = res.scalar()
        res2 = await conn.execute(text("SELECT count(*) FROM players WHERE discord_id IS NOT NULL"))
        c2 = res2.scalar()
        print(f"DEV DB memberships count: {c}")
        print(f"DEV DB linked players count: {c2}")
if __name__ == '__main__':
    asyncio.run(main())
