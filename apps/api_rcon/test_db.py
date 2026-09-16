import asyncio
from sqlmodel import select
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.orm import sessionmaker
import sys
import json

sys.path.append(r'd:\proyectos_dev\server_rcon_automation\apps\api_rcon')
from src.connections.databases.db import Player, Membership

async def main():
    engine = create_async_engine('postgresql+asyncpg://postgres:password@localhost:5432/wardogs')
    SessionLocal = sessionmaker(engine, class_=AsyncSession)
    async with SessionLocal() as session:
        sid = '76561198055320029'
        mems = (await session.exec(select(Membership).where(Membership.steam_id == sid))).all()
        print(f"Memberships for {sid}:")
        for m in mems:
            print(f"- ID: {m.id}, Type: {m.membership_type}, Active: {m.is_active}, End: {m.end_time}")

asyncio.run(main())
