import asyncio
from sqlmodel import select, col
from typing import Optional

from src.connections.databases.db import engine, Player, Match, MatchPlayerStats, PlayerSession, Team, MatchTeamStats, BotConfig
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

                    # 50v50 Mode lifecycle transition on new match
                    stmt_state = select(BotConfig).where(BotConfig.config_key == "MODE_50V50_STATE")
                    cfg_state = (await session.exec(stmt_state)).first()
                    if cfg_state and cfg_state.config_value:
                        cur_state = cfg_state.config_value.strip().lower()
                        if cur_state == "pending_enable":
                            cfg_state.config_value = "active"
                            session.add(cfg_state)
                            cfg_en = await session.get(BotConfig, "MODE_50V50_ENABLED")
                            if cfg_en:
                                cfg_en.config_value = "true"
                                session.add(cfg_en)
                            else:
                                session.add(BotConfig(config_key="MODE_50V50_ENABLED", config_value="true"))
                            logger.info("[50v50 Mode] New match started! 50v50 Mode is now ACTIVE.")
                            try:
                                await rcon_client.broadcast("Modo 50v50 ACTIVADO para esta partida (Rojo vs Verde)!")
                            except Exception:
                                pass
                        elif cur_state == "pending_disable":
                            cfg_state.config_value = "inactive"
                            session.add(cfg_state)
                            cfg_en = await session.get(BotConfig, "MODE_50V50_ENABLED")
                            if cfg_en:
                                cfg_en.config_value = "false"
                                session.add(cfg_en)
                            else:
                                session.add(BotConfig(config_key="MODE_50V50_ENABLED", config_value="false"))
                            logger.info("[50v50 Mode] New match started! 50v50 Mode is now INACTIVE.")
                            try:
                                await rcon_client.broadcast("Modo 50v50 FINALIZADO. Volviendo a 33v33v33.")
                            except Exception:
                                pass
                
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


# In-memory dict to track recently transferred players and prevent ping-ponging
recently_swapped_players: dict[str, float] = {}

async def mode_50v50_loop():
    logger.info("Starting 50v50 Mode Engine (Checks every 6 seconds)...")
    while True:
        try:
            is_enabled = False
            async with AsyncSession(engine) as session:
                stmt_state = select(BotConfig).where(BotConfig.config_key == "MODE_50V50_STATE")
                config_state = (await session.exec(stmt_state)).first()
                if config_state and config_state.config_value:
                    is_enabled = config_state.config_value.strip().lower() in ("active", "pending_disable")
                else:
                    stmt = select(BotConfig).where(BotConfig.config_key == "MODE_50V50_ENABLED")
                    config = (await session.exec(stmt)).first()
                    if config and config.config_value:
                        val = config.config_value.strip().lower()
                        is_enabled = val in ("true", "1", "enabled", "yes", "on")

            if is_enabled:
                now_ts = time.time()
                # Purge expired cooldowns (> 120 seconds)
                expired = [sid for sid, ts in recently_swapped_players.items() if now_ts - ts > 120]
                for sid in expired:
                    del recently_swapped_players[sid]

                # Dynamically resolve exact faction names from live server status (e.g. "Valkyra" vs "Valkyre")
                red_name = "Valkyra"
                green_name = "Manticore"
                try:
                    status_resp = await rcon_client.get_status()
                    if status_resp and status_resp.factionScores:
                        for fs in status_resp.factionScores:
                            fn = (fs.name or "").strip()
                            if fn.lower().startswith("valk"):
                                red_name = fn
                            elif fn.lower().startswith("mant"):
                                green_name = fn
                except Exception as err_status:
                    logger.warning(f"[50v50 Mode] Could not get live faction names from status: {err_status}")

                players_resp = await rcon_client.get_players()
                all_players = players_resp.players or []
                
                blue_players = []
                red_players = []
                green_players = []
                
                for p in all_players:
                    f = (p.faction or "").strip().lower()
                    if f.startswith("lone"):
                        blue_players.append(p)
                    elif f.startswith("valk"):
                        red_players.append(p)
                    elif f.startswith("mant"):
                        green_players.append(p)
                    # NOTE: Players with "white" or spectator/none factions are strictly ignored
                
                # Step 1: Transfer any players in Lonestar (Blue) to whichever team is smaller
                if blue_players:
                    logger.info(f"[50v50 Mode] Found {len(blue_players)} players in Lonestar (Blue). Transferring... ({red_name}={len(red_players)}, {green_name}={len(green_players)})")
                    for p in blue_players:
                        if not p.steamId:
                            continue
                        if len(red_players) <= len(green_players):
                            target_faction = red_name
                            red_players.append(p)
                        else:
                            target_faction = green_name
                            green_players.append(p)
                            
                        try:
                            await rcon_client.switch_faction(p.steamId, target_faction)
                            recently_swapped_players[p.steamId] = now_ts
                            logger.info(f"[50v50 Mode] Moved {p.name} ({p.steamId}) from Lonestar -> {target_faction}")
                        except Exception as err:
                            logger.error(f"[50v50 Mode] Failed to move {p.steamId} to {target_faction}: {err}")

                # Step 2: Auto-teambalancing between Red and Green (since in-game balancing is unlocked)
                # If difference is >= 2, move the newest players (lowest cash, lowest stats) from larger to smaller
                diff = len(red_players) - len(green_players)
                if abs(diff) >= 2:
                    count_to_move = abs(diff) // 2
                    if diff > 0:
                        donor_team = red_players
                        target_faction = green_name
                        donor_name = red_name
                    else:
                        donor_team = green_players
                        target_faction = red_name
                        donor_name = green_name

                    # Sort candidates: prioritize newest players (lowest cash, then lowest kills+deaths)
                    # Exclude players who were recently swapped within last 60 seconds
                    candidates = [p for p in donor_team if p.steamId and (now_ts - recently_swapped_players.get(p.steamId, 0) > 60)]
                    # If all candidates have cooldown, allow any candidate with steamId
                    if not candidates:
                        candidates = [p for p in donor_team if p.steamId]

                    # Sort key: 1) cash (0 cash first), 2) kills + deaths, 3) kills
                    candidates.sort(key=lambda p: (
                        p.cash if p.cash is not None else 0,
                        (p.kills or 0) + (p.deaths or 0),
                        p.kills or 0
                    ))

                    logger.info(f"[50v50 Mode] Teambalance triggered! {donor_name} has {len(donor_team)} vs {target_faction} ({len(donor_team) - abs(diff)}). Moving {count_to_move} newest player(s)...")

                    for p in candidates[:count_to_move]:
                        try:
                            await rcon_client.switch_faction(p.steamId, target_faction)
                            recently_swapped_players[p.steamId] = now_ts
                            logger.info(f"[50v50 Mode] Rebalanced {p.name} ({p.steamId}, cash=${p.cash or 0}, K/D={p.kills or 0}/{p.deaths or 0}) {donor_name} -> {target_faction}")
                        except Exception as err:
                            logger.error(f"[50v50 Mode] Failed to rebalance {p.steamId} to {target_faction}: {err}")

        except Exception as e:
            logger.error(f"[50v50 Mode] Error in 50v50 loop: {e}")

        await asyncio.sleep(6)


