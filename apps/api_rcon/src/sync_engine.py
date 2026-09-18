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

# In-memory tracking across polls
last_rcon_player_stats: dict[str, dict] = {}
player_team_history: dict[str, dict] = {}
recently_swapped_players: dict[str, float] = {}

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

                    # Clear in-memory match tracking for fresh match
                    last_rcon_player_stats.clear()
                    player_team_history.clear()
                    recently_swapped_players.clear()

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
                            
                        # 2. Update MatchPlayerStats with resilience to stat resets on team change
                        if current_match_id:
                            team_id = None
                            if p.faction:
                                faction_name = str(p.faction).strip()
                                code_3 = faction_name[:3].upper()
                                t_stmt = select(Team).where((Team.name == faction_name) | (Team.code == code_3))
                                team = (await session.exec(t_stmt)).first()
                                if not team:
                                    team = Team(name=faction_name, code=code_3)
                                    session.add(team)
                                    await session.commit()
                                    await session.refresh(team)
                                team_id = team.id

                            # Handle server stat resets (if game resets kills/deaths/cash when player switches team)
                            raw_kills = p.kills or 0
                            raw_deaths = p.deaths or 0
                            raw_cash = p.cash or 0
                            p_faction_str = str(p.faction or "")
                            
                            tracker = last_rcon_player_stats.setdefault(p.steamId, {
                                "last_raw_kills": raw_kills,
                                "last_raw_deaths": raw_deaths,
                                "last_raw_cash": raw_cash,
                                "offset_kills": 0,
                                "offset_deaths": 0,
                                "offset_cash": 0,
                                "last_faction": p_faction_str
                            })
                            
                            # If raw values dropped (e.g. server reset stats on faction change), accumulate offset
                            if raw_kills < tracker["last_raw_kills"]:
                                tracker["offset_kills"] += tracker["last_raw_kills"]
                                logger.info(f"[Stats Engine] Server reset kills for {p.steamId} on faction change ({tracker['last_raw_kills']} -> {raw_kills}). Accumulated offset: {tracker['offset_kills']}")
                                
                            if raw_deaths < tracker["last_raw_deaths"]:
                                tracker["offset_deaths"] += tracker["last_raw_deaths"]

                            if raw_cash < tracker["last_raw_cash"]:
                                tracker["offset_cash"] += tracker["last_raw_cash"]
                                logger.info(f"[Stats Engine] Server reset cash for {p.steamId} on faction change ({tracker['last_raw_cash']} -> {raw_cash}). Accumulated cash offset: {tracker['offset_cash']}")
                                
                            tracker["last_raw_kills"] = raw_kills
                            tracker["last_raw_deaths"] = raw_deaths
                            tracker["last_raw_cash"] = raw_cash
                            tracker["last_faction"] = p_faction_str
                            
                            effective_kills = tracker["offset_kills"] + raw_kills
                            effective_deaths = tracker["offset_deaths"] + raw_deaths
                            effective_cash = tracker["offset_cash"] + raw_cash

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
                                    kills=effective_kills,
                                    deaths=effective_deaths,
                                    cash_earned=effective_cash
                                )
                            else:
                                stats.kills = effective_kills
                                stats.deaths = effective_deaths
                                stats.team_id = team_id
                                if effective_cash > stats.cash_earned:
                                    stats.cash_earned = effective_cash
                            
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
                                fs_name = str(fs.name).strip()
                                code_3 = fs_name[:3].upper()
                                t_stmt = select(Team).where((Team.name == fs_name) | (Team.code == code_3))
                                team = (await session.exec(t_stmt)).first()
                                if not team:
                                    team = Team(name=fs_name, code=code_3)
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
                        f_canonical = "lonestar"
                    elif f.startswith("valk"):
                        f_canonical = "valkyra"
                    elif f.startswith("mant"):
                        f_canonical = "manticore"
                    else:
                        # NOTE: Players with "white" or spectator/none factions are strictly ignored
                        continue

                    # Update player team tenure and prevent unpermitted voluntary team switches
                    if p.steamId and f_canonical in ("valkyra", "manticore"):
                        hist = player_team_history.get(p.steamId)
                        if not hist:
                            # First time seen on a team in this match -> Register initial assigned team!
                            player_team_history[p.steamId] = {
                                "current_faction": f_canonical,
                                "assigned_faction": f_canonical,
                                "joined_team_at": now_ts,
                            }
                        else:
                            if hist["current_faction"] != f_canonical:
                                old_f = hist["current_faction"]
                                bot_swapped = (now_ts - recently_swapped_players.get(p.steamId, 0)) < 15

                                # ARMA-STYLE STRICT LOCK: If player manually switched between Red and Green, block & revert!
                                if not bot_swapped:
                                    assigned = hist.get("assigned_faction", old_f)
                                    if assigned in ("valkyra", "manticore") and assigned != f_canonical:
                                        revert_target = red_name if assigned == "valkyra" else green_name
                                        logger.warning(f"[50v50 Mode] Player {p.name} ({p.steamId}) attempted manual team switch from {assigned} -> {f_canonical}! Blocking and reverting back to {revert_target}...")
                                        try:
                                            await rcon_client.switch_faction(p.steamId, revert_target)
                                            recently_swapped_players[p.steamId] = now_ts
                                            await rcon_client.send_player_message(p.steamId, "Cambio de equipo no permitido durante la partida.")
                                        except Exception as err_revert:
                                            logger.error(f"[50v50 Mode] Failed to revert unpermitted team switch for {p.steamId}: {err_revert}")
                                        if assigned == "valkyra":
                                            red_players.append(p)
                                        else:
                                            green_players.append(p)
                                        continue

                                hist["current_faction"] = f_canonical
                                hist["joined_team_at"] = now_ts

                        if f_canonical == "valkyra":
                            red_players.append(p)
                        else:
                            green_players.append(p)
                
                # Step 1: Transfer any players in Lonestar (Blue) to whichever team is smaller
                if blue_players:
                    logger.info(f"[50v50 Mode] Found {len(blue_players)} players in Lonestar (Blue). Transferring... ({red_name}={len(red_players)}, {green_name}={len(green_players)})")
                    for p in blue_players:
                        if not p.steamId:
                            continue
                        if len(red_players) <= len(green_players):
                            target_faction = red_name
                            target_key = "valkyra"
                            red_players.append(p)
                        else:
                            target_faction = green_name
                            target_key = "manticore"
                            green_players.append(p)
                            
                        try:
                            await rcon_client.switch_faction(p.steamId, target_faction)
                            recently_swapped_players[p.steamId] = now_ts
                            player_team_history[p.steamId] = {
                                "current_faction": target_key,
                                "assigned_faction": target_key,
                                "joined_team_at": now_ts,
                            }
                            logger.info(f"[50v50 Mode] Moved {p.name} ({p.steamId}) from Lonestar -> {target_faction}")
                            try:
                                await rcon_client.send_player_message(p.steamId, f"Se te ha asignado al equipo {target_faction}.")
                            except Exception:
                                pass
                        except Exception as err:
                            logger.error(f"[50v50 Mode] Failed to move {p.steamId} to {target_faction}: {err}")

                # Step 2: Auto-teambalancing between Red and Green (since in-game balancing is unlocked)
                # If difference is >= 2, move fresh non-combatant arrivals from larger to smaller
                diff = len(red_players) - len(green_players)
                if abs(diff) >= 2:
                    count_to_move = abs(diff) // 2
                    if diff > 0:
                        donor_team = red_players
                        target_faction = green_name
                        target_key = "manticore"
                        donor_name = red_name
                    else:
                        donor_team = green_players
                        target_faction = red_name
                        target_key = "valkyra"
                        donor_name = green_name

                    # STRICT FAIRNESS RULE:
                    # Original veterans who chose their team (or were assigned from Blue) and have combated
                    # (cash > 0 or K/D > 0) are 100% IMMUNE from being forced to the other team when players ragequit.
                    # ONLY fresh arrivals without combat footprint ($0 cash and 0 kills and 0 deaths) are eligible.
                    # Exclude any player currently in the 60s swap cooldown.
                    eligible_candidates = []
                    for p in donor_team:
                        if not p.steamId:
                            continue
                        if (now_ts - recently_swapped_players.get(p.steamId, 0)) <= 60:
                            continue

                        has_combat_footprint = ((p.cash or 0) > 0) or ((p.kills or 0) > 0) or ((p.deaths or 0) > 0)
                        if not has_combat_footprint:
                            eligible_candidates.append(p)

                    if not eligible_candidates:
                        logger.info(f"[50v50 Mode] Teambalance: {donor_name} has {len(donor_team)} vs {target_faction} ({len(donor_team) - abs(diff)}), but all players on {donor_name} are protected original veterans. Keeping teams as-is until new players connect.")
                    else:
                        # Sort eligible fresh candidates by newest join time (-joined_team_at)
                        def candidate_sort_key(p):
                            hist = player_team_history.get(p.steamId, {})
                            joined_at = hist.get("joined_team_at", now_ts)
                            return -joined_at

                        eligible_candidates.sort(key=candidate_sort_key)
                        actual_move = min(count_to_move, len(eligible_candidates))

                        logger.info(f"[50v50 Mode] Teambalance triggered! {donor_name} has {len(donor_team)} vs {target_faction} ({len(donor_team) - abs(diff)}). Moving {actual_move} eligible fresh candidate(s)...")

                        for p in eligible_candidates[:actual_move]:
                            try:
                                await rcon_client.switch_faction(p.steamId, target_faction)
                                recently_swapped_players[p.steamId] = now_ts
                                player_team_history[p.steamId] = {
                                    "current_faction": target_key,
                                    "assigned_faction": target_key,
                                    "joined_team_at": now_ts,
                                }
                                logger.info(f"[50v50 Mode] Rebalanced {p.name} ({p.steamId}, cash=${p.cash or 0}, K/D={p.kills or 0}/{p.deaths or 0}) {donor_name} -> {target_faction}")
                                try:
                                    await rcon_client.send_player_message(p.steamId, f"Se te ha asignado al equipo {target_faction} para balancear la partida.")
                                except Exception:
                                    pass
                            except Exception as err:
                                logger.error(f"[50v50 Mode] Failed to rebalance {p.steamId} to {target_faction}: {err}")

        except Exception as e:
            logger.error(f"[50v50 Mode] Error in 50v50 loop: {e}")

        await asyncio.sleep(6)


