from fastapi import FastAPI
import asyncio
from contextlib import asynccontextmanager
from dotenv import load_dotenv

from src.modules import V1_ROUTER
from src.connections.apis.rcon import rcon_client

load_dotenv()

from src.sync_engine import poll_rcon, mode_50v50_loop
from src.modules.v1.router import sync_memberships
from src.modules.v1.services.backup_service import create_database_backup, get_available_backups
from src.config import ENVIRONMENT_SETTINGS
from src.connections.databases.db import engine
from sqlmodel.ext.asyncio.session import AsyncSession

polling_task = None
maintenance_task = None
mode_50v50_task = None
backup_task = None

async def db_maintenance_loop():
    while True:
        try:
            async with AsyncSession(engine) as session:
                await sync_memberships(session=session)
        except Exception as e:
            print(f"[Maintenance] Error syncing memberships: {e}")
        await asyncio.sleep(300) # Every 5 minutes

async def db_backup_loop():
    await asyncio.sleep(15)
    interval_hours = ENVIRONMENT_SETTINGS.CONNECTIONS_SETTINGS.BACKUP_INTERVAL_HOURS
    interval_seconds = max(3600, interval_hours * 3600)

    if not get_available_backups():
        try:
            async with AsyncSession(engine) as session:
                await create_database_backup(session=session)
                print("[Backup] Initial database backup completed.")
        except Exception as e:
            print(f"[Backup] Error during initial backup: {e}")

    while True:
        try:
            await asyncio.sleep(interval_seconds)
            async with AsyncSession(engine) as session:
                await create_database_backup(session=session)
                print("[Backup] Scheduled database backup completed.")
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[Backup] Error in scheduled backup: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    global polling_task, maintenance_task, mode_50v50_task, backup_task
    polling_task = asyncio.create_task(poll_rcon())
    maintenance_task = asyncio.create_task(db_maintenance_loop())
    mode_50v50_task = asyncio.create_task(mode_50v50_loop())
    backup_task = asyncio.create_task(db_backup_loop())
    yield
    if polling_task:
        polling_task.cancel()
    if maintenance_task:
        maintenance_task.cancel()
    if mode_50v50_task:
        mode_50v50_task.cancel()
    if backup_task:
        backup_task.cancel()

app = FastAPI(title="Wardogs RCON API", version="1.0.0", lifespan=lifespan)

app.include_router(V1_ROUTER, prefix="/api")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
