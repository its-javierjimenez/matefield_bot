import asyncio
from sqlmodel import select
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.orm import sessionmaker
import sys

sys.path.append(r'd:\proyectos_dev\server_rcon_automation\apps\api_rcon')
from src.connections.databases.db import Player, Membership

async def main():
    engine = create_async_engine('postgresql+asyncpg://postgres:password@localhost:5432/wardogs')
    SessionLocal = sessionmaker(engine, class_=AsyncSession)
    async with SessionLocal() as session:
        for sid in ['76561198444633735', '76561199130881242', '76561199084731031']:
            mems = (await session.exec(select(Membership).where(Membership.steam_id == sid))).all()
            for m in mems:
                print(f"Steam: {sid}, Active: {m.is_active}, Sync: {m.rcon_sync_status}, End: {m.end_time}")

asyncio.run(main())
