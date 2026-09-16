import asyncio
from sqlmodel import select
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.orm import sessionmaker
import sys

sys.path.append(r'd:\proyectos_dev\server_rcon_automation\apps\api_rcon')
from src.connections.databases.db import Role

async def main():
    engine = create_async_engine('postgresql+asyncpg://postgres:password@localhost:5432/wardogs')
    SessionLocal = sessionmaker(engine, class_=AsyncSession)
    async with SessionLocal() as session:
        roles = (await session.exec(select(Role))).all()
        for r in roles:
            print(f"Role: {r.id}, Name: {r.name}, Managed: {r.is_managed}")
            
asyncio.run(main())
