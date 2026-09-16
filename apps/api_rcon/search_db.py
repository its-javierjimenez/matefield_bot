import asyncio
from sqlmodel import select
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.orm import sessionmaker
import sys

sys.path.append(r'd:\proyectos_dev\server_rcon_automation\apps\api_rcon')
from src.connections.databases.db import Player, Membership, PlayerRole, Role

async def main():
    engine = create_async_engine('postgresql+asyncpg://postgres:password@localhost:5432/wardogs')
    SessionLocal = sessionmaker(engine, class_=AsyncSession)
    async with SessionLocal() as session:
        sid = '76561198091537355'
        p = await session.get(Player, sid)
        if not p:
            print("Player not found in DB!")
            return
        print(f"Player: {p.in_game_name}, Discord: {p.discord_id}")
        
        mems = (await session.exec(select(Membership).where(Membership.steam_id == sid))).all()
        for m in mems:
            print(f"- Membership: {m.membership_type}, Active: {m.is_active}, End: {m.end_time}, Sync: {m.rcon_sync_status}")
            
asyncio.run(main())
