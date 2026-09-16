from fastapi import FastAPI
import asyncio
from contextlib import asynccontextmanager
from dotenv import load_dotenv

from src.modules import V1_ROUTER
from src.connections.apis.rcon import rcon_client

load_dotenv()

from src.sync_engine import poll_rcon
from src.modules.v1.router import sync_memberships
from src.connections.databases.db import engine
from sqlmodel.ext.asyncio.session import AsyncSession

polling_task = None
maintenance_task = None

async def db_maintenance_loop():
    while True:
        try:
            async with AsyncSession(engine) as session:
                await sync_memberships(session=session)
        except Exception as e:
            print(f"[Maintenance] Error syncing memberships: {e}")
        await asyncio.sleep(300) # Every 5 minutes

@asynccontextmanager
async def lifespan(app: FastAPI):
    global polling_task, maintenance_task
    polling_task = asyncio.create_task(poll_rcon())
    maintenance_task = asyncio.create_task(db_maintenance_loop())
    yield
    if polling_task:
        polling_task.cancel()
    if maintenance_task:
        maintenance_task.cancel()

app = FastAPI(title="Wardogs RCON API", version="1.0.0", lifespan=lifespan)

app.include_router(V1_ROUTER, prefix="/api")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
