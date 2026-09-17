import asyncio
from sqlmodel import select, func, col
from src.connections.databases.db import Membership, get_session

async def check_duplicates():
    async for session in get_session():
        stmt = select(Membership.steam_id, func.count(col(Membership.id))).group_by(Membership.steam_id).having(func.count(col(Membership.id)) > 1) # type: ignore
        dups = (await session.exec(stmt)).all()
        
        print(f"Encontrados {len(dups)} steam_ids con multiples membresias.")
        
        for steam_id, count in dups[:5]:
            m_stmt = select(Membership).where(Membership.steam_id == steam_id).order_by(col(Membership.id)) # type: ignore
            memberships = (await session.exec(m_stmt)).all()
            print(f"\nSteam ID: {steam_id}")
            for m in memberships:
                print(f"  ID: {m.id} | Type: {m.membership_type} | Active: {m.is_active} | Start: {m.start_time} | End: {m.end_time}")

if __name__ == "__main__":
    asyncio.run(check_duplicates())
