import asyncio
from sqlmodel import select
from typing import Optional

from src.connections.databases.db import engine, Player, Match, MatchPlayerStats, PlayerSession, Team, MatchTeamStats
from sqlmodel.ext.asyncio.session import AsyncSession
from src.connections.apis.rcon import rcon_client
import datetime
import logging

# State
current_rotation_index: Optional[int] = None
current_match_id: Optional[str] = None
current_map: Optional[str] = None

logger = logging.getLogger("sync_engine")
logger.setLevel(logging.INFO)
# Basic config if not already set by FastAPI
if not logger.handlers:
    ch = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

async def poll_rcon():
    global current_rotation_index, current_match_id, current_map
    
    logger.info("Starting RCON Polling Engine...")
    last_poll_time = datetime.datetime.now(datetime.timezone.utc)
    
    while True:
        try:
            now = datetime.datetime.now(datetime.timezone.utc)
            delta_seconds = int((now - last_poll_time).total_seconds())
            
            # Bug 1 Fix: Prevent time leaps if the polling loop was blocked or delayed
            if delta_seconds > 60:
                logger.warning(f"[Match Engine] Large time gap detected ({delta_seconds}s). Capping to 60s.")
                delta_seconds = 60
                
            last_poll_time = now
            
            status = await rcon_client.get_status()
            players = await rcon_client.get_players()
            
            # Determine if we have a match rotation
            rotation_index = status.rotation.nowIndex if status.rotation else None
            map_name = status.map or "Unknown"
            
            async with AsyncSession(engine) as session:
                # Check for match start/change
                if current_match_id is None or rotation_index != current_rotation_index:
                    logger.info(f"[Match Engine] Match transition! Old map: {current_map}, New map: {map_name} (Rotation {rotation_index})")
                    
                    # Close old match if it exists
                    if current_match_id:
                        old_match = await session.get(Match, current_match_id)
                        if old_match and old_match.end_time is None:
                            old_match.end_time = datetime.datetime.now(datetime.timezone.utc)
                            # We don't know winning team without explicit scores, maybe leave null
                            session.add(old_match)
                    
                    # Start new match
                    match_seconds = status.matchSeconds or 0
                    real_start_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=match_seconds)
                    
                    new_match = Match(
                        map_name=map_name,
                        start_time=real_start_time
                    )
                    session.add(new_match)
                    await session.commit()
                    await session.refresh(new_match)
                    
                    current_match_id = new_match.id
                    current_rotation_index = rotation_index
                    current_map = map_name
                
                # Sync players
                if players and players.players:
                    for p in players.players:
                        if not p.steamId:
                            continue
                            
                        # 1. Ensure Player exists
                        db_player = await session.get(Player, p.steamId)
                        if not db_player:
                            db_player = Player(steam_id=p.steamId, discord_id=None)
                            session.add(db_player)
                            await session.commit()
                            
                        # 2. Update MatchPlayerStats
                        if current_match_id:
                            # Bug 2 Fix: Extract Team ID from player faction
                            team_id = None
                            if p.faction:
                                faction_name = str(p.faction)
                                t_stmt = select(Team).where(Team.name == faction_name)
                                team = (await session.exec(t_stmt)).first()
                                if not team:
                                    team = Team(name=faction_name, code=faction_name[:3].upper())
                                    session.add(team)
                                    await session.commit()
                                    await session.refresh(team)
                                team_id = team.id

                            stmt = select(MatchPlayerStats).where(
                                MatchPlayerStats.match_id == current_match_id,
                                MatchPlayerStats.steam_id == p.steamId
                            )
                            stats = (await session.exec(stmt)).first()
                            if not stats:
                                stats = MatchPlayerStats(
                                    match_id=current_match_id,
                                    steam_id=p.steamId,
                                    team_id=team_id,
                                    kills=p.kills or 0,
                                    deaths=p.deaths or 0,
                                    cash_earned=p.cash or 0
                                )
                            else:
                                # Update kills/deaths cumulatively
                                stats.kills = p.kills or 0
                                stats.deaths = p.deaths or 0
                                stats.team_id = team_id
                                
                                # Track highest watermark for cash_earned to avoid resetting when buying vehicles
                                current_cash = p.cash or 0
                                if current_cash > stats.cash_earned:
                                    stats.cash_earned = current_cash
                            
                            session.add(stats)
                            
                    # Session Tracking Logic
                    current_players = (status.players.current or 0) if status.players else 0
                    is_seeding = current_players < 20
                    current_steam_ids = {p.steamId for p in players.players if p.steamId}
                    
                    active_sessions_stmt = select(PlayerSession).where(PlayerSession.end_time == None)
                    active_sessions = (await session.exec(active_sessions_stmt)).all()
                    
                    active_session_dict = {s.steam_id: s for s in active_sessions}
                    
                    for s in active_sessions:
                        if s.steam_id in current_steam_ids:
                            s.total_seconds += delta_seconds
                            if is_seeding:
                                s.seeding_seconds += delta_seconds
                            session.add(s)
                        else:
                            # Use total_seconds to calculate actual end time, preventing huge gaps if engine restarts
                            s.end_time = s.start_time + datetime.timedelta(seconds=s.total_seconds)
                            session.add(s)
                            
                    for sid in current_steam_ids:
                        if sid not in active_session_dict:
                            new_sess = PlayerSession(steam_id=sid, start_time=now)
                            session.add(new_sess)
                            
                    # Match Team Stats & End Detection
                    if current_match_id and status.factionScores:
                        score_cap = status.scoreCap or 100
                        match_record = await session.get(Match, current_match_id)
                        if match_record and match_record.end_time is None:
                            max_score = 0
                            winning_team_id = None
                            
                            for fs in status.factionScores:
                                if not fs.name:
                                    continue
                                
                                # Get or create Team
                                t_stmt = select(Team).where(Team.name == fs.name)
                                team = (await session.exec(t_stmt)).first()
                                if not team:
                                    team = Team(name=fs.name, code=fs.name[:3].upper())
                                    session.add(team)
                                    await session.commit()
                                    await session.refresh(team)
                                    
                                # Update Team Stats
                                ts_stmt = select(MatchTeamStats).where(
                                    MatchTeamStats.match_id == current_match_id,
                                    MatchTeamStats.team_id == team.id
                                )
                                t_stat = (await session.exec(ts_stmt)).first()
                                if not t_stat:
                                    if team.id is None:
                                        continue
                                    t_stat = MatchTeamStats(match_id=current_match_id, team_id=team.id, score=int(fs.score or 0))
                                    session.add(t_stat)
                                else:
                                    t_stat.score = int(fs.score or 0)
                                    session.add(t_stat)
                                    
                                if (fs.score or 0) >= max_score:
                                    max_score = fs.score or 0
                                    winning_team_id = team.id
                                    
                            if max_score >= score_cap:
                                logger.info(f"[Match Engine] Match ended! Score {max_score} >= {score_cap}")
                                match_record.end_time = now
                                match_record.winning_team_id = winning_team_id
                                session.add(match_record)

                    await session.commit()

            # Dynamic polling rate
            sleep_time = 10
            if status.scoreTick and status.scoreCap:
                tick_current = status.scoreTick.current or 0
                if tick_current >= (status.scoreCap - 3):
                    sleep_time = 3
                    
            await asyncio.sleep(sleep_time)

        except Exception as e:
            logger.error(f"[Match Engine] Error polling RCON in sync_engine: {e}")
            await asyncio.sleep(10)
