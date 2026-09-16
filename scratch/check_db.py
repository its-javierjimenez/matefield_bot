import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

PROD_DB = "postgresql+asyncpg://u163006579_CgWGlvgFAC:Ahlz8ZR9qUpn3TqrI9RVgMUE@gamessao1079.bisecthosting.com:5432/s163006579_matefield_prod"

async def main():
    engine = create_async_engine(PROD_DB)
    async with engine.begin() as conn:
        res = await conn.execute(text("SELECT * FROM players WHERE discord_id = '240644979393953792'"))
        player = res.fetchone()
        print(f"Player: {player}")
        if player:
            steam_id = player[1] # assuming steam_id is col 1
            res = await conn.execute(text(f"SELECT * FROM memberships WHERE steam_id = '{steam_id}'"))
            mems = res.fetchall()
            print(f"Memberships: {mems}")
        
        res = await conn.execute(text("SELECT count(*) FROM memberships"))
        c = res.scalar()
        print(f"Total memberships in PROD: {c}")

if __name__ == '__main__':
    asyncio.run(main())
