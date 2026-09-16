import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

PROD_DB = "postgresql+asyncpg://u163006579_CgWGlvgFAC:Ahlz8ZR9qUpn3TqrI9RVgMUE@gamessao1079.bisecthosting.com:5432/s163006579_matefield_prod"

async def main():
    engine = create_async_engine(PROD_DB)
    async with engine.begin() as conn:
        # Check ALL memberships (active AND inactive)
        r = await conn.execute(text("""
            SELECT m.id, m.steam_id, m.type, m.start_date, m.end_date, m.is_active, p.discord_id
            FROM memberships m
            LEFT JOIN players p ON m.steam_id = p.steam_id
            WHERE m.is_active = false
            ORDER BY m.end_date
        """))
        inactive = r.fetchall()
        
        print(f"=== MEMBRESIAS INACTIVAS ({len(inactive)}) ===")
        for row in inactive:
            print(f"  ID:{row[0]} Steam:{row[1]} Tipo:{row[2]} Inicio:{row[3]} Fin:{row[4]} Discord:{row[6]}")
        
        # Check bot_config completely
        r = await conn.execute(text("SELECT * FROM bot_config"))
        configs = r.fetchall()
        print(f"\n=== BOT_CONFIG ({len(configs)}) ===")
        for row in configs:
            print(f"  {row[0]} = {row[1]}")

if __name__ == '__main__':
    asyncio.run(main())
