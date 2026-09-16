import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

url = "postgresql+asyncpg://u163006579_K9hF1DxFjM:vBZLroJdlUBLSDWZvByeWP4n@gamessao1079.bisecthosting.com:5432/s163006579_matefield_dev"
async def main():
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        res = await conn.execute(text("SELECT datname FROM pg_database"))
        dbs = res.fetchall()
        print("Databases:", [d[0] for d in dbs])

if __name__ == '__main__':
    asyncio.run(main())
