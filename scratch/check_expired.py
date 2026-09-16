import asyncio
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

PROD_DB = "postgresql+asyncpg://u163006579_CgWGlvgFAC:Ahlz8ZR9qUpn3TqrI9RVgMUE@gamessao1079.bisecthosting.com:5432/s163006579_matefield_prod"

async def main():
    engine = create_async_engine(PROD_DB)
    now = datetime.now(timezone.utc)
    print(f"Hora actual UTC: {now}\n")
    
    async with engine.begin() as conn:
        # Memberships that are active but have expired end_date
        r = await conn.execute(text("""
            SELECT m.id, m.steam_id, m.type, m.start_date, m.end_date, m.is_active, p.discord_id
            FROM memberships m
            LEFT JOIN players p ON m.steam_id = p.steam_id
            WHERE m.is_active = true AND m.end_date IS NOT NULL AND m.end_date < :now
            ORDER BY m.end_date
        """), {"now": now})
        expired_active = r.fetchall()
        
        print(f"=== MEMBRESIAS VENCIDAS PERO AUN ACTIVAS ({len(expired_active)}) ===")
        for row in expired_active:
            print(f"  ID:{row[0]} Steam:{row[1]} Tipo:{row[2]} Fin:{row[4]} Discord:{row[6]}")
        
        print()
        
        # All active memberships
        r = await conn.execute(text("""
            SELECT m.id, m.steam_id, m.type, m.end_date, m.is_active, p.discord_id
            FROM memberships m
            LEFT JOIN players p ON m.steam_id = p.steam_id
            WHERE m.is_active = true
            ORDER BY m.end_date NULLS LAST
        """))
        active = r.fetchall()
        print(f"=== MEMBRESIAS ACTIVAS TOTALES ({len(active)}) ===")
        for row in active:
            end = row[3] if row[3] else "PERMANENTE"
            print(f"  ID:{row[0]} Steam:{row[1]} Tipo:{row[2]} Fin:{end} Discord:{row[5]}")

        # Check the column names
        r = await conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'memberships' ORDER BY ordinal_position"))
        cols = [row[0] for row in r.fetchall()]
        print(f"\nColumnas de memberships: {cols}")

if __name__ == '__main__':
    asyncio.run(main())
