import asyncio
from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import text
import src.connections.databases.db as db_models

DEV_DB = "postgresql+asyncpg://u163006579_K9hF1DxFjM:vBZLroJdlUBLSDWZvByeWP4n@gamessao1079.bisecthosting.com:5432/s163006579_matefield_dev"
PROD_DB = "postgresql+asyncpg://u163006579_CgWGlvgFAC:Ahlz8ZR9qUpn3TqrI9RVgMUE@gamessao1079.bisecthosting.com:5432/s163006579_matefield_prod"

async def main():
    dev_engine = create_async_engine(DEV_DB)
    prod_engine = create_async_engine(PROD_DB)
    
    print("Creating tables in PROD...")
    async with prod_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)
        
    print("Fetching data from DEV...")
    data = {}
    async with AsyncSession(dev_engine) as dev_session:
        # Tables to copy
        tables = [
            "bot_config",
            "roles",
            "players",
            "memberships",
            "player_roles",
            "membership_type_configs",
            "bans"
        ]
        
        for name in tables:
            res = await dev_session.execute(text(f"SELECT * FROM {name}"))
            rows = res.fetchall()
            if rows:
                keys = list(res.keys())
                data[name] = [dict(zip(keys, row)) for row in rows]
            else:
                data[name] = []
            print(f"Fetched {len(data[name])} rows from {name}")
            
    print("Inserting data into PROD...")
    async with prod_engine.begin() as prod_conn:
        for name in tables:
            rows = data[name]
            if rows:
                keys = list(rows[0].keys())
                cols = ", ".join(keys)
                vals = ", ".join([f":{k}" for k in keys])
                stmt = text(f"INSERT INTO {name} ({cols}) VALUES ({vals})")
                await prod_conn.execute(stmt, rows)
                print(f"Inserted {len(rows)} rows into {name}")

    print("Truncating match tables in DEV...")
    async with dev_engine.begin() as dev_conn:
        for t in ["match_player_stats", "match_team_stats", "player_sessions", "teams", "matches"]:
            await dev_conn.execute(text(f"TRUNCATE TABLE {t} CASCADE"))
        print("Dev match tables truncated.")
        
    print("Done!")

if __name__ == '__main__':
    asyncio.run(main())
