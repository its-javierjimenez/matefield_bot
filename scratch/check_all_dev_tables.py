import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
url = "postgresql+asyncpg://u163006579_K9hF1DxFjM:vBZLroJdlUBLSDWZvByeWP4n@gamessao1079.bisecthosting.com:5432/s163006579_matefield_dev"
async def main():
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        res = await conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'"))
        tables = [r[0] for r in res.fetchall()]
        for t in tables:
            c_res = await conn.execute(text(f"SELECT count(*) FROM {t}"))
            print(f"{t}: {c_res.scalar()}")
if __name__ == '__main__':
    asyncio.run(main())
