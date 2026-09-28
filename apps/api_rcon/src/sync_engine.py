import asyncio
from sqlmodel import select, col, or_
from typing import Optional, Any

from src.connections.databases.db import engine, Player, Match, MatchPlayerStats, PlayerSession, Team, MatchTeamStats, BotConfig
from sqlmodel.ext.asyncio.session import AsyncSession
from src.connections.apis.rcon import rcon_client
from src.connections.apis.steam import get_player_summary
from src.modules.v1.services.rewards_service import RewardsService
import datetime
import logging

class SyncEngineState:
    """Encapsulates the in-memory state of match tracking and map rotations."""
    def __init__(self):
        self.current_rotation_index: Optional[int] = None
        self.current_match_id: Optional[str] = None
        self.current_map: Optional[str] = None

default_sync_state = SyncEngineState()

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
    team = (await session.exec(select(Team).where(Team.name == name))).first()
    if not team:
        code = name[:3].upper() if len(name) >= 3 else name.upper()
        existing_code = (await session.exec(select(Team).where(Team.code == code))).first()
        if existing_code:
            code = f"{name[:2].upper()}{len(name)}"[:3]
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


async def process_sync_tick(
    session: AsyncSession,
    status: Any,
    players: Any,
    now: datetime.datetime,
    delta_seconds: int,
    state: Optional[SyncEngineState] = None,
) -> dict[str, Any]:
    """
    Processes a single game server polling tick:
    1. Handles match rotation & start/end lifecycle.
    2. Upserts connected player records and match player statistics.
    3. Manages player sessions and calculates seeding rewards (runs even if 0 players online to close sessions).
    4. Tracks team scores and detects match win/completion.
    """
    if state is None:
        state = default_sync_state

    rotation_index = status.rotation.nowIndex if (status and status.rotation) else None
    map_name = (status.map if status else None) or "Unknown"

    # 1. Check for match start/transition
    match_transitioned = False
    if state.current_match_id is None or rotation_index != state.current_rotation_index:
        logger.info(f"[Match Engine] Match transition! Old map: {state.current_map}, New map: {map_name} (Rotation {rotation_index})")
        match_transitioned = True
        
        # Close old match if it exists and hasn't been closed yet
        if state.current_match_id:
            old_match = await session.get(Match, state.current_match_id)
            if old_match and old_match.end_time is None:
                old_match.end_time = now
                winner_stmt = select(MatchTeamStats).where(MatchTeamStats.match_id == state.current_match_id).order_by(col(MatchTeamStats.score).desc())
                winner_stat = (await session.exec(winner_stmt)).first()
                if winner_stat:
                    old_match.winning_team_id = winner_stat.team_id
                session.add(old_match)

        # Start new match
        match_seconds = (status.matchSeconds or 0) if status else 0
        real_start_time = now - datetime.timedelta(seconds=match_seconds)
        new_match = Match(
            map_name=map_name,
            start_time=real_start_time
        )
        session.add(new_match)
        await session.flush()
        
        state.current_match_id = new_match.id
        state.current_rotation_index = rotation_index
        state.current_map = map_name

    # 2. Sync players & player stats
    current_players_list = players.players if (players and players.players) else []
    for p in current_players_list:
        if not p.steamId:
            continue
            
        db_player = await session.get(Player, p.steamId)
        if not db_player:
            db_player = Player(steam_id=p.steamId, discord_id=None, in_game_name=p.name)
            session.add(db_player)
            await session.flush()
        elif p.name and db_player.in_game_name != p.name:
            db_player.in_game_name = p.name
            session.add(db_player)
            
        if state.current_match_id:
            team_id = await _get_or_create_team(session, p.faction)
            stmt = select(MatchPlayerStats).where(
                MatchPlayerStats.match_id == state.current_match_id,
                MatchPlayerStats.steam_id == p.steamId
            )
            stats = (await session.exec(stmt)).first()
            if not stats:
                stats = MatchPlayerStats(
                    match_id=state.current_match_id,
                    steam_id=p.steamId,
                    team_id=team_id,
                    kills=p.kills or 0,
                    deaths=p.deaths or 0,
                    cash_earned=p.cash or 0
                )
            else:
                stats.kills = p.kills or 0
                stats.deaths = p.deaths or 0
                stats.team_id = team_id
                current_cash = p.cash or 0
                if current_cash > stats.cash_earned:
                    stats.cash_earned = current_cash
            session.add(stats)

    # 3. Session Tracking & Seeding Rewards (Runs EVEN if 0 players online to properly close sessions)
    seeding_threshold = await _get_int_config(session, "SEEDING_MIN_PLAYERS", DEFAULT_SEEDING_MIN_PLAYERS)
    minutes_per_point = await _get_int_config(session, "SEEDING_MINUTES_PER_POINT", DEFAULT_SEEDING_MINUTES_PER_POINT)

    current_players_count = (status.players.current or 0) if (status and status.players) else len(current_players_list)
    is_seeding = current_players_count < seeding_threshold
    current_steam_ids = {p.steamId for p in current_players_list if p.steamId}

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
            # Player disconnected: Close session using accumulated total_seconds
            s.end_time = s.start_time + datetime.timedelta(seconds=s.total_seconds)
            session.add(s)

    for sid in current_steam_ids:
        if sid not in active_session_dict:
            new_sess = PlayerSession(steam_id=sid, start_time=now)
            session.add(new_sess)
            asyncio.create_task(_fetch_avatar_background(sid))

    # 4. Match Team Stats & End Detection
    match_ended = False
    if state.current_match_id and status and status.factionScores:
        score_cap = status.scoreCap or DEFAULT_SCORE_CAP
        match_record = await session.get(Match, state.current_match_id)
        if match_record and match_record.end_time is None:
            max_score = 0
            winning_team_id = None
            
            for fs in status.factionScores:
                if not fs.name:
                    continue
                team_id = await _get_or_create_team(session, fs.name)
                if not team_id:
                    continue
                    
                ts_stmt = select(MatchTeamStats).where(
                    MatchTeamStats.match_id == state.current_match_id,
                    MatchTeamStats.team_id == team_id
                )
                t_stat = (await session.exec(ts_stmt)).first()
                score_val = int(fs.score or 0)
                if not t_stat:
                    t_stat = MatchTeamStats(match_id=state.current_match_id, team_id=team_id, score=score_val)
                    session.add(t_stat)
                else:
                    t_stat.score = score_val
                    session.add(t_stat)
                    
                if score_val >= max_score:
                    max_score = score_val
                    winning_team_id = team_id
                    
            if max_score >= score_cap:
                logger.info(f"[Match Engine] Match ended! Score {max_score} >= {score_cap}")
                match_record.end_time = now
                match_record.winning_team_id = winning_team_id
                session.add(match_record)
                match_ended = True

    await session.commit()
    return {
        "match_id": state.current_match_id,
        "match_transitioned": match_transitioned,
        "match_ended": match_ended,
        "active_players_count": len(current_steam_ids),
        "is_seeding": is_seeding,
    }


async def poll_rcon(state: Optional[SyncEngineState] = None):
    """Continuous polling loop querying game server status and processing sync ticks."""
    if state is None:
        state = default_sync_state
    
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
            
            async with AsyncSession(engine) as session:
                await process_sync_tick(session, status, players, now, delta_seconds, state=state)

            # Dynamic polling rate: poll faster near match end
            sleep_time = DEFAULT_POLL_INTERVAL_SECONDS
            if status and status.scoreTick and status.scoreCap:
                tick_current = status.scoreTick.current or 0
                if tick_current >= (status.scoreCap - FAST_POLL_TICKS_REMAINING):
                    sleep_time = FAST_POLL_INTERVAL_SECONDS
                    
            await asyncio.sleep(sleep_time)

        except Exception as e:
            logger.error(f"[Match Engine] Error polling RCON in sync_engine: {e}")
            await asyncio.sleep(DEFAULT_POLL_INTERVAL_SECONDS)
