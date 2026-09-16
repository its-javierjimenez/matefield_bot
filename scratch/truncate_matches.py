import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

PROD_DB = "postgresql+asyncpg://u163006579_CgWGlvgFAC:Ahlz8ZR9qUpn3TqrI9RVgMUE@gamessao1079.bisecthosting.com:5432/s163006579_matefield_prod"

async def main():
    engine = create_async_engine(PROD_DB)
    async with engine.begin() as conn:
        print("Truncating match_player_stats, match_team_stats, matches, teams...")
        await conn.execute(text("TRUNCATE TABLE match_player_stats, match_team_stats, matches, teams CASCADE"))
        print("Done.")

if __name__ == '__main__':
    asyncio.run(main())
