import asyncio
from sqlmodel import select
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.orm import sessionmaker
import sys

sys.path.append(r'd:\proyectos_dev\server_rcon_automation\apps\api_rcon')
from src.connections.databases.db import Role, PlayerRole, Membership

async def main():
    engine = create_async_engine('postgresql+asyncpg://postgres:password@localhost:5432/wardogs')
    SessionLocal = sessionmaker(engine, class_=AsyncSession)
    async with SessionLocal() as session:
        # Fix Memberships types
        mems = (await session.exec(select(Membership))).all()
        for m in mems:
            if m.membership_type == 'MENSUAL':
                m.membership_type = 'VIP_COMUN'
                session.add(m)
            elif m.membership_type == 'PERMANENTE':
                m.membership_type = 'VIP_PERMANENTE'
                session.add(m)
        
        # Fix Fundador role
        # We have Role id=1 name='1546690312762564648' (the correct one)
        # and another Role name='Fundador' (the wrong one I created)
        
        correct_role = (await session.exec(select(Role).where(Role.name == '1546690312762564648'))).first()
        wrong_role = (await session.exec(select(Role).where(Role.name == 'Fundador'))).first()
        
        if wrong_role and correct_role:
            # Move all PlayerRole links from wrong to correct
            links = (await session.exec(select(PlayerRole).where(PlayerRole.role_id == wrong_role.id))).all()
            for link in links:
                # Check if it already has the correct role
                existing = (await session.exec(select(PlayerRole).where(PlayerRole.role_id == correct_role.id, PlayerRole.steam_id == link.steam_id))).first()
                if not existing:
                    link.role_id = correct_role.id
                    session.add(link)
                else:
                    await session.delete(link)
            
            # Delete wrong role
            await session.delete(wrong_role)
            
        await session.commit()
        print('Database fixed!')

asyncio.run(main())
