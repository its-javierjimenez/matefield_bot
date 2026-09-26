import logging
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from dotenv import load_dotenv

load_dotenv()

from src.modules import V1_ROUTER
from src.connections.apis.rcon import RCONManager
from src.sync_engine import poll_rcon
from src.modules.v1.services.memberships_service import MembershipsService
from src.modules.v1.services.backup_service import create_database_sql_backup
from src.connections.databases.db import engine
from sqlmodel.ext.asyncio.session import AsyncSession

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("wardogs.api")

polling_task: asyncio.Task | None = None
maintenance_task: asyncio.Task | None = None
backup_task: asyncio.Task | None = None

async def db_maintenance_loop():
    while True:
        try:
            async with AsyncSession(engine) as session:
                await MembershipsService.sync_memberships_logic(session)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"[Maintenance] Error syncing memberships: {e}", exc_info=True)
        await asyncio.sleep(300) # Every 5 minutes

async def db_backup_loop():
    try:
        await asyncio.sleep(30) # Initial delay on startup
    except asyncio.CancelledError:
        return
    while True:
        try:
            async with AsyncSession(engine) as session:
                await create_database_sql_backup(session)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"[Backup] Error creating automated SQL backup: {e}", exc_info=True)
        await asyncio.sleep(43200) # Every 12 hours

@asynccontextmanager
async def lifespan(app: FastAPI):
    global polling_task, maintenance_task, backup_task
    polling_task = asyncio.create_task(poll_rcon())
    maintenance_task = asyncio.create_task(db_maintenance_loop())
    backup_task = asyncio.create_task(db_backup_loop())
    logger.info("Application background services started.")
    yield
    tasks = [t for t in (polling_task, maintenance_task, backup_task) if t is not None]
    for t in tasks:
        t.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    await RCONManager.close_all()
    logger.info("Application background services and RCON connection pools shut down.")

app = FastAPI(title="Wardogs RCON API", version="1.0.0", lifespan=lifespan)

from pathlib import Path
from fastapi.staticfiles import StaticFiles

STATIC_DIR = Path(__file__).resolve().parents[1] / "static"
if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.mount("/api/static", StaticFiles(directory=str(STATIC_DIR)), name="api_static")

app.include_router(V1_ROUTER, prefix="/api")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
