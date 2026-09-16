import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from src.connections.apis.rcon import RCONClient
from src.core.config import get_environment_settings

env = get_environment_settings()
rcon = RCONClient(
    host=env.RCON_SETTINGS.RCON_HOST,
    port=env.RCON_SETTINGS.RCON_PORT,
    password=env.RCON_SETTINGS.RCON_PASSWORD
)

PROD_DB = "postgresql+asyncpg://u163006579_CgWGlvgFAC:Ahlz8ZR9qUpn3TqrI9RVgMUE@gamessao1079.bisecthosting.com:5432/s163006579_matefield_prod"

async def main():
    engine = create_async_engine(PROD_DB)
    async with engine.begin() as conn:
        r = await conn.execute(text("SELECT DISTINCT steam_id FROM memberships WHERE is_active = true"))
        active_steam_ids = set([row[0] for row in r.fetchall()])
        
        r_inactive = await conn.execute(text("SELECT DISTINCT steam_id FROM memberships WHERE is_active = false"))
        inactive_steam_ids = set([row[0] for row in r_inactive.fetchall()]) - active_steam_ids
        
    try:
        current_slots_resp = await rcon.get_reserved_slots()
        current_slots = set(current_slots_resp.reservedSlots or [])
    except Exception as e:
        print(f"Error connecting to RCON: {e}")
        return

    synced = list(active_steam_ids.intersection(current_slots))
    pending_add = list(active_steam_ids - current_slots)
    pending_remove = list(current_slots - active_steam_ids)
    inactive_in_rcon = list(inactive_steam_ids.intersection(current_slots))

    print(f"=== ESTADO RCON RESERVED SLOTS ===")
    print(f"Jugadores activos en DB: {len(active_steam_ids)}")
    print(f"Slots reservados en RCON: {len(current_slots)}")
    print(f"Sincronizados (Correctos): {len(synced)}")
    print(f"Faltan agregar a RCON: {len(pending_add)}")
    print(f"Sobran en RCON (para remover): {len(pending_remove)}")
    print(f"De los cuales, tienen membresía INACTIVA en DB: {len(inactive_in_rcon)}")
    
    if pending_remove:
        print("\nEjemplos que sobran en RCON (deberían removerse):")
        for s in pending_remove[:10]: print(f"  {s}")

if __name__ == '__main__':
    asyncio.run(main())
