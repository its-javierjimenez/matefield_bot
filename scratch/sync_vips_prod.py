import asyncio
import csv
from datetime import datetime
from sqlmodel import select
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.orm import sessionmaker
import sys
import os

sys.path.append(r"d:\proyectos_dev\matefield_bot\apps\api_rcon")
from src.connections.databases.db import Player, Membership, Role, PlayerRole

PROD_DB = "postgresql+asyncpg://u163006579_CgWGlvgFAC:Ahlz8ZR9qUpn3TqrI9RVgMUE@gamessao1079.bisecthosting.com:5432/s163006579_matefield_prod"
engine = create_async_engine(PROD_DB)
SessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

CSV_FILE = r"d:\proyectos_dev\matefield_bot\docs\excel_history\VIP MATEFIELD - Registro VIP.csv"

def parse_date(date_str):
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str.strip(), "%Y-%m-%d")
    except ValueError:
        return None

async def main():
    async with SessionLocal() as session:
        # Check/create "Fundador" role
        stmt = select(Role).where(Role.name == "Fundador")
        fundador_role = (await session.exec(stmt)).first()
        if not fundador_role:
            fundador_role = Role(name="Fundador", rcon_rank="Fundador")
            session.add(fundador_role)
            await session.commit()
            await session.refresh(fundador_role)
        
        with open(CSV_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                steam_id = row.get("ID STEAM", "").strip()
                if not steam_id:
                    continue
                
                discord_id = row.get("ID DISCORD", "").strip()
                discord_id = discord_id if discord_id else None
                
                observaciones = row.get("OBSERVACIONES", "").strip()
                if not observaciones:
                    observaciones = None
                
                es_fundador = (row.get("ES FUNDADOR", "").strip().upper() == "SI")
                tipo_vip = row.get("TIPO VIP", "").strip()
                
                # Player upsert
                player = await session.get(Player, steam_id)
                if not player:
                    player = Player(steam_id=steam_id)
                    session.add(player)
                
                # Check for discord_id collision
                if discord_id:
                    stmt_coll = select(Player).where(Player.discord_id == discord_id, Player.steam_id != steam_id)
                    coll = (await session.exec(stmt_coll)).first()
                    if coll:
                        print(f"WARN: Discord ID {discord_id} already linked to another player {coll.steam_id}. Unlinking.")
                        coll.discord_id = None
                        session.add(coll)
                        
                player.discord_id = discord_id
                
                if observaciones:
                    player.observations = observaciones
                    
                session.add(player)
                await session.flush()
                
                # Role assignment
                if es_fundador:
                    # check if already linked
                    stmt_link = select(PlayerRole).where(PlayerRole.steam_id == steam_id, PlayerRole.role_id == fundador_role.id)
                    link = (await session.exec(stmt_link)).first()
                    if not link:
                        new_link = PlayerRole(steam_id=steam_id, role_id=fundador_role.id)
                        session.add(new_link)
                
                # Membership assignment
                if tipo_vip:
                    # Inactivate old memberships
                    stmt_mems = select(Membership).where(Membership.steam_id == steam_id, Membership.is_active == True)
                    mems = (await session.exec(stmt_mems)).all()
                    for m in mems:
                        m.is_active = False
                        session.add(m)
                    
                    fecha_inicio = parse_date(row.get("Fecha inicio"))
                    
                    fecha_fin = parse_date(row.get("FINAL"))
                    if not fecha_fin:
                        fecha_fin = parse_date(row.get("Fecha fin"))
                        
                    if tipo_vip.upper() == "PERMANENTE":
                        fecha_fin = None
                        
                    new_mem = Membership(
                        steam_id=steam_id,
                        membership_type=tipo_vip,
                        start_time=fecha_inicio,
                        end_time=fecha_fin,
                        is_active=True
                    )
                    session.add(new_mem)
                
                print(f"Processed {row.get('USUARIO')} ({steam_id}) - Fundador: {es_fundador} - Obs: {observaciones is not None}")
        
        await session.commit()
        print("Done!")

if __name__ == "__main__":
    asyncio.run(main())
