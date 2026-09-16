import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

PROD_DB = "postgresql+asyncpg://u163006579_CgWGlvgFAC:Ahlz8ZR9qUpn3TqrI9RVgMUE@gamessao1079.bisecthosting.com:5432/s163006579_matefield_prod"

async def main():
    engine = create_async_engine(PROD_DB)
    async with engine.begin() as conn:
        # Check the model column names vs DB column names
        # The code uses "end_time" but the DB column is "end_date"
        print("=== MODELO vs BD ===")
        r = await conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'memberships' ORDER BY ordinal_position"))
        cols = [row[0] for row in r.fetchall()]
        print(f"DB columns: {cols}")
        
        # Check bot_config for ROLE_MAP entries
        r = await conn.execute(text("SELECT config_key, config_value FROM bot_config WHERE config_key LIKE 'ROLE_MAP_%'"))
        maps = r.fetchall()
        print(f"\n=== ROLE_MAP CONFIG ({len(maps)}) ===")
        for row in maps:
            print(f"  {row[0]} = {row[1]}")
        
        if not maps:
            print("  !! VACIO - NO HAY MAPEO DE ROLES !!")
            print("  Sin esto, el bot NO SABE qué rol de Discord corresponde a cada tipo de membresía")

if __name__ == '__main__':
    asyncio.run(main())
