import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

PROD_DB = "postgresql+asyncpg://u163006579_CgWGlvgFAC:Ahlz8ZR9qUpn3TqrI9RVgMUE@gamessao1079.bisecthosting.com:5432/s163006579_matefield_prod"

configs = [
    ("VIP_ROLE_IDS", "1546845168169259060,1546846355656417311,1546690312762564648"),
    ("ROLE_MAP_VIP_COMUN", "1546845168169259060"),
    ("ROLE_DAYS_VIP_COMUN", "30"),
    ("ROLE_MAP_VIP_EXPRESS", "1546846355656417311"),
    ("ROLE_DAYS_VIP_EXPRESS", "15"),
    ("ROLE_MAP_VIP_PERMANENTE", "1548089245195968572"),
    ("ROLE_DAYS_VIP_PERMANENTE", "0"),
    ("ROLE_MAP_VIP_SEED", "1546846355656417311"),
    ("ROLE_DAYS_VIP_SEED", "3"),
]

async def main():
    engine = create_async_engine(PROD_DB)
    async with engine.begin() as conn:
        for key, val in configs:
            await conn.execute(text(
                "INSERT INTO bot_config (config_key, config_value) VALUES (:k, :v) ON CONFLICT (config_key) DO UPDATE SET config_value = :v"
            ), {"k": key, "v": val})
            print(f"  {key} = {val}")
    
    # Verify
    async with engine.begin() as conn:
        r = await conn.execute(text("SELECT * FROM bot_config ORDER BY config_key"))
        rows = r.fetchall()
        print(f"\n=== VERIFICACION ({len(rows)} configs) ===")
        for row in rows:
            print(f"  {row[0]} = {row[1]}")

if __name__ == '__main__':
    asyncio.run(main())
