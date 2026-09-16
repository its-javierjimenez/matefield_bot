import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

PROD_DB = "postgresql+asyncpg://u163006579_CgWGlvgFAC:Ahlz8ZR9qUpn3TqrI9RVgMUE@gamessao1079.bisecthosting.com:5432/s163006579_matefield_prod"

async def main():
    engine = create_async_engine(PROD_DB)
    async with engine.begin() as conn:
        r = await conn.execute(text("SELECT id, name FROM roles"))
        print("=== Roles in DB ===")
        for row in r.fetchall():
            print(f"  id={row[0]}, name={row[1]}")
        
        r2 = await conn.execute(text("SELECT steam_id, role_id FROM player_roles"))
        print("\n=== Player Roles ===")
        for row in r2.fetchall():
            print(f"  steam_id={row[0]}, role_id={row[1]}")

if __name__ == '__main__':
    asyncio.run(main())
