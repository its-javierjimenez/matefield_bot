import asyncio
from sqlmodel import select, col, or_
from typing import Optional

from src.connections.databases.db import engine, Player, Match, MatchPlayerStats, PlayerSession, Team, MatchTeamStats, BotConfig
from sqlmodel.ext.asyncio.session import AsyncSession
from src.connections.apis.rcon import rcon_client
from src.connections.apis.steam import get_player_summary
from src.modules.v1.services.rewards_service import RewardsService
import datetime
import logging

# State
current_rotation_index: Optional[int] = None
current_match_id: Optional[str] = None
current_map: Optional[str] = None

# Polling and game sync constants
MAX_TIME_GAP_SECONDS = 60
DEFAULT_POLL_INTERVAL_SECONDS = 10
FAST_POLL_INTERVAL_SECONDS = 3
FAST_POLL_TICKS_REMAINING = 3
DEFAULT_SEEDING_MIN_PLAYERS = 20
DEFAULT_SEEDING_MINUTES_PER_POINT = 30
DEFAULT_SCORE_CAP = 100

logger = logging.getLogger("sync_engine")
logger.setLevel(logging.INFO)
# Basic config if not already set by FastAPI
if not logger.handlers:
    ch = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)


async def _get_int_config(session: AsyncSession, key: str, default: int) -> int:
    """Reads a numeric configuration from BotConfig with safe fallback."""
    cfg = await session.get(BotConfig, key)
    if cfg and cfg.config_value:
        try:
            return int(cfg.config_value)
        except (ValueError, TypeError):
            pass
    return default


async def _get_or_create_team(session: AsyncSession, faction_name: Optional[str]) -> Optional[int]:
    """Resolves or inserts a Team entity by name or short 3-letter code."""
    if not faction_name:
        return None
    name = str(faction_name).strip()
    if not name:
        return None
    code = name[:3].upper() if len(name) >= 3 else name.upper()
    t_stmt = select(Team).where(or_(Team.name == name, Team.code == code))
    team = (await session.exec(t_stmt)).first()
    if not team:
        team = Team(name=name, code=code)
        session.add(team)
        await session.flush()
        await session.refresh(team)
    return team.id


async def _fetch_avatar_background(steam_id: str):
    try:
        summary = await get_player_summary(steam_id)
        if summary:
            avatar = summary.get("avatarfull") or summary.get("avatarmedium")
            personaname = summary.get("personaname")
            if avatar or personaname:
                async with AsyncSession(engine) as s:
                    p = await s.get(Player, steam_id)
                    if p:
                        changed = False
                        if avatar and not p.avatar_url:
                            p.avatar_url = avatar
                            changed = True
                        if personaname and not p.in_game_name:
                            p.in_game_name = personaname
                            changed = True
                        if changed:
                            s.add(p)
                            await s.commit()
    except Exception as e:
        logger.debug(f"[Sync Engine] Could not fetch steam profile for {steam_id}: {e}")

async def poll_rcon():
    global current_rotation_index, current_match_id, current_map
    
    logger.info("Starting RCON Polling Engine...")
    last_poll_time = datetime.datetime.now(datetime.timezone.utc)
    
    while True:
        try:
            now = datetime.datetime.now(datetime.timezone.utc)
            delta_seconds = int((now - last_poll_time).total_seconds())
            
            # Prevent time leaps if the polling loop was blocked or delayed
            if delta_seconds > MAX_TIME_GAP_SECONDS:
                logger.warning(f"[Match Engine] Large time gap detected ({delta_seconds}s). Capping to {MAX_TIME_GAP_SECONDS}s.")
                delta_seconds = MAX_TIME_GAP_SECONDS
                
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
                            # Determine winning team from last known MatchTeamStats
                            winner_stmt = select(MatchTeamStats).where(MatchTeamStats.match_id == current_match_id).order_by(col(MatchTeamStats.score).desc())
                            winner_stat = (await session.exec(winner_stmt)).first()
                            if winner_stat:
                                old_match.winning_team_id = winner_stat.team_id
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
                            
                        # 1. Ensure Player exists & update in_game_name
                        db_player = await session.get(Player, p.steamId)
                        if not db_player:
                            db_player = Player(steam_id=p.steamId, discord_id=None, in_game_name=p.name)
                            session.add(db_player)
                            await session.flush()
                        elif p.name and db_player.in_game_name != p.name:
                            db_player.in_game_name = p.name
                            session.add(db_player)
                            
                        # 2. Update MatchPlayerStats
                        if current_match_id:
                            team_id = await _get_or_create_team(session, p.faction)

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
                            
                    # Session Tracking & Rewards Logic
                    seeding_threshold = await _get_int_config(session, "SEEDING_MIN_PLAYERS", DEFAULT_SEEDING_MIN_PLAYERS)
                    minutes_per_point = await _get_int_config(session, "SEEDING_MINUTES_PER_POINT", DEFAULT_SEEDING_MINUTES_PER_POINT)

                    current_players = (status.players.current or 0) if status.players else 0
                    is_seeding = current_players < seeding_threshold
                    current_steam_ids = {p.steamId for p in players.players if p.steamId}
                    
                    active_sessions_stmt = select(PlayerSession).where(PlayerSession.end_time == None)
                    active_sessions = (await session.exec(active_sessions_stmt)).all()
                    
                    active_session_dict = {s.steam_id: s for s in active_sessions}
                    
                    for s in active_sessions:
                        if s.steam_id in current_steam_ids:
                            db_p = await session.get(Player, s.steam_id)
                            if db_p:
                                RewardsService.process_session_seeding(
                                    session_obj=s,
                                    player_obj=db_p,
                                    delta_seconds=delta_seconds,
                                    is_seeding=is_seeding,
                                    minutes_per_point=minutes_per_point,
                                )
                                session.add(db_p)
                            else:
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
                            asyncio.create_task(_fetch_avatar_background(sid))
                            
                    # Match Team Stats & End Detection
                    if current_match_id and status.factionScores:
                        score_cap = status.scoreCap or DEFAULT_SCORE_CAP
                        match_record = await session.get(Match, current_match_id)
                        if match_record and match_record.end_time is None:
                            max_score = 0
                            winning_team_id = None
                            
                            for fs in status.factionScores:
                                if not fs.name:
                                    continue
                                
                                team_id = await _get_or_create_team(session, fs.name)
                                if not team_id:
                                    continue
                                    
                                # Update Team Stats
                                ts_stmt = select(MatchTeamStats).where(
                                    MatchTeamStats.match_id == current_match_id,
                                    MatchTeamStats.team_id == team_id
                                )
                                t_stat = (await session.exec(ts_stmt)).first()
                                if not t_stat:
                                    t_stat = MatchTeamStats(match_id=current_match_id, team_id=team_id, score=int(fs.score or 0))
                                    session.add(t_stat)
                                else:
                                    t_stat.score = int(fs.score or 0)
                                    session.add(t_stat)
                                    
                                if (fs.score or 0) >= max_score:
                                    max_score = fs.score or 0
                                    winning_team_id = team_id
                                    
                            if max_score >= score_cap:
                                logger.info(f"[Match Engine] Match ended! Score {max_score} >= {score_cap}")
                                match_record.end_time = now
                                match_record.winning_team_id = winning_team_id
                                session.add(match_record)

                    await session.commit()

            # Dynamic polling rate: poll faster near match end
            sleep_time = DEFAULT_POLL_INTERVAL_SECONDS
            if status.scoreTick and status.scoreCap:
                tick_current = status.scoreTick.current or 0
                if tick_current >= (status.scoreCap - FAST_POLL_TICKS_REMAINING):
                    sleep_time = FAST_POLL_INTERVAL_SECONDS
                    
            await asyncio.sleep(sleep_time)

        except Exception as e:
            logger.error(f"[Match Engine] Error polling RCON in sync_engine: {e}")
            await asyncio.sleep(DEFAULT_POLL_INTERVAL_SECONDS)
