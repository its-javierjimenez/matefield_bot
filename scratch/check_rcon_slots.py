import asyncio
import aiohttp
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
import os

PROD_DB = "postgresql+asyncpg://u163006579_CgWGlvgFAC:Ahlz8ZR9qUpn3TqrI9RVgMUE@gamessao1079.bisecthosting.com:5432/s163006579_matefield_prod"
rcon_url = "http://169.155.127.77:9001"
rcon_pass = "dVt2ajQzYqGKnDft"

async def main():
    engine = create_async_engine(PROD_DB)
    async with engine.begin() as conn:
        r = await conn.execute(text("SELECT DISTINCT steam_id FROM memberships WHERE is_active = true"))
        active_steam_ids = set([row[0] for row in r.fetchall()])
        
        r_inactive = await conn.execute(text("SELECT DISTINCT steam_id FROM memberships WHERE is_active = false"))
        inactive_steam_ids = set([row[0] for row in r_inactive.fetchall()]) - active_steam_ids

    print(f"--- FETCHING FROM {rcon_url}/v1/reserved-slots ---")
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{rcon_url}/v1/reserved-slots", headers={"Authorization": f"Bearer {rcon_pass}"}) as resp:
            if resp.status == 200:
                data = await resp.json()
                current_slots = set(data.get("reservedSlots", []))
            else:
                print(f"Failed to fetch RCON: {resp.status} - {await resp.text()}")
                return

    synced = list(active_steam_ids.intersection(current_slots))
    pending_add = list(active_steam_ids - current_slots)
    pending_remove = list(current_slots - active_steam_ids)
    inactive_in_rcon = list(inactive_steam_ids.intersection(current_slots))

    print(f"=== ESTADO RCON RESERVED SLOTS ===")
    print(f"Jugadores activos en DB: {len(active_steam_ids)}")
    print(f"Slots reservados en RCON: {len(current_slots)}")
    print(f"Sincronizados (Correctos): {len(synced)}")
    print(f"Faltan agregar a RCON (tienen VIP y no slot): {len(pending_add)}")
    print(f"Sobran en RCON (tienen slot y NO tienen VIP activo): {len(pending_remove)}")
    print(f"  --> De los cuales, tienen membresía INACTIVA en DB: {len(inactive_in_rcon)}")
    
    if pending_remove:
        print("\nEjemplos de gente que SOBRA en RCON (deberían removerse):")
        for s in pending_remove[:10]: print(f"  {s}")
        
    if pending_add:
        print("\nEjemplos de gente que FALTA en RCON (deberían agregarse):")
        for s in pending_add[:10]: print(f"  {s}")

if __name__ == '__main__':
    asyncio.run(main())
