import asyncio
import asyncpg

PROD_DB = "postgresql://u163006579_CgWGlvgFAC:Ahlz8ZR9qUpn3TqrI9RVgMUE@gamessao1079.bisecthosting.com:5432/s163006579_matefield_prod"

async def main():
    conn = await asyncpg.connect(PROD_DB)
    try:
        await conn.execute("ALTER TABLE bans ADD COLUMN expires_at TIMESTAMP WITH TIME ZONE;")
        print("Column added successfully.")
    except Exception as e:
        print(f"Error adding column: {e}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
