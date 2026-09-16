import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

PROD_DB = "postgresql+asyncpg://u163006579_CgWGlvgFAC:Ahlz8ZR9qUpn3TqrI9RVgMUE@gamessao1079.bisecthosting.com:5432/s163006579_matefield_prod"

async def main():
    engine = create_async_engine(PROD_DB)
    async with engine.begin() as conn:
        r = await conn.execute(text("SELECT steam_id FROM players"))
        rows = r.fetchall()
        for row in rows:
            steam_id = row[0]
            # check memberships
            rm = await conn.execute(text("SELECT type FROM memberships WHERE steam_id = :s AND is_active = true"), {"s": steam_id})
            mem = [m[0] for m in rm.fetchall()]
            
            # check roles
            rr = await conn.execute(text("SELECT role_id FROM player_roles WHERE steam_id = :s"), {"s": steam_id})
            role_ids = [r[0] for r in rr.fetchall()]
            role_names = []
            for rid in role_ids:
                rn = await conn.execute(text("SELECT name FROM roles WHERE id = :id"), {"id": rid})
                role_names.append(rn.scalar())
            
            if "ADMIN" in mem or any("ADMIN" in str(rn).upper() for rn in role_names) or "76561198893379466" in str(steam_id):
                print(f"SteamID: {steam_id}, Memberships: {mem}, Roles: {role_names}")

if __name__ == '__main__':
    asyncio.run(main())
