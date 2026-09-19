import asyncio
import time
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
last_match_seconds: Optional[int] = None
server_was_reconnected: bool = False

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
    global current_rotation_index, current_match_id, current_map, last_match_seconds, server_was_reconnected

    
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
            
            # Determine if we have a match rotation or server reboot
            rotation_index = status.rotation.nowIndex if status.rotation else None
            map_name = status.map or "Unknown"
            match_seconds = status.matchSeconds if status.matchSeconds is not None else 0

            # Detect new match / rotation / server reboot:
            # 1. First poll ever (current_match_id is None)
            # 2. Rotation index changed (rotation_index != current_rotation_index)
            # 3. Map changed directly (current_map is not None and map_name != current_map)
            # 4. Match clock dropped significantly (server reboot or match restart on same map)
            # 5. Server was offline and reconnected (server_was_reconnected)
            is_new_match = (
                current_match_id is None
                or (rotation_index is not None and rotation_index != current_rotation_index)
                or (current_map is not None and map_name != current_map)
                or (last_match_seconds is not None and (match_seconds < (last_match_seconds - 5) or (match_seconds <= 15 and last_match_seconds > 20)))
                or server_was_reconnected
            )
            server_was_reconnected = False
            last_match_seconds = match_seconds
            
            async with AsyncSession(engine) as session:
                # Check for match start/change
                if is_new_match:
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
                            await session.commit()
                            logger.info("[50v50 Mode] New match started! 50v50 Mode is now ACTIVE.")
                            try:
                                await rcon_client.set_team_balancing(False)
                            except Exception:
                                pass
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
                            await session.commit()
                            logger.info("[50v50 Mode] New match started! 50v50 Mode is now INACTIVE.")
                            try:
                                await rcon_client.set_team_balancing(True, threshold=1)
                            except Exception:
                                pass
                            try:
                                await rcon_client.broadcast("Modo 50v50 FINALIZADO. Volviendo a 33v33v33.")
                            except Exception:
                                pass
                        elif cur_state == "active":
                            try:
                                await rcon_client.broadcast("Modo 50v50 ACTIVADO para esta partida (Rojo vs Verde)!")
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
            server_was_reconnected = True
            await asyncio.sleep(10)


async def mode_50v50_loop():
    logger.info("Starting 50v50 Mode Engine (Checks every 6 seconds)...")
    warmup_10s_sent = False
    active_broadcast_sent = False
    last_50v50_match_id = None

    while True:
        try:
            is_enabled = False
            async with AsyncSession(engine) as session:
                stmt_state = select(BotConfig).where(BotConfig.config_key == "MODE_50V50_STATE")
                config_state = (await session.exec(stmt_state)).first()
                if config_state and config_state.config_value:
                    st = config_state.config_value.strip().lower()
                    is_enabled = st in ("active", "pending_disable")
                else:
                    stmt = select(BotConfig).where(BotConfig.config_key == "MODE_50V50_ENABLED")
                    config = (await session.exec(stmt)).first()
                    if config and config.config_value:
                        val = config.config_value.strip().lower()
                        is_enabled = val in ("true", "1", "enabled", "yes", "on")

            if is_enabled:
                now_ts = time.time()

                # Dynamically resolve exact faction names and matchSeconds from live server status
                red_name = "Valkyra"
                green_name = "Manticore"
                match_seconds = None
                try:
                    status_resp = await rcon_client.get_status()
                    if status_resp:
                        match_seconds = getattr(status_resp, "matchSeconds", None)
                        if status_resp.factionScores:
                            for fs in status_resp.factionScores:
                                fn = (fs.name or "").strip()
                                if fn.lower().startswith("valk"):
                                    red_name = fn
                                elif fn.lower().startswith("mant"):
                                    green_name = fn
                except Exception as err_status:
                    logger.warning(f"[50v50 Mode] Could not get live faction names from status: {err_status}")

                # Reset tracking on new match transition
                if current_match_id != last_50v50_match_id:
                    logger.info(f"[50v50 Mode] New match detected ({current_match_id}). Resetting team tracking & broadcasts.")
                    last_50v50_match_id = current_match_id
                    player_team_history.clear()
                    recently_swapped_players.clear()
                    warmup_10s_sent = False
                    active_broadcast_sent = False
                elif match_seconds is not None and match_seconds < 10 and active_broadcast_sent:
                    # In-place match restart on same match/map
                    logger.info("[50v50 Mode] In-place match restart detected. Resetting team tracking & broadcasts.")
                    player_team_history.clear()
                    recently_swapped_players.clear()
                    warmup_10s_sent = False
                    active_broadcast_sent = False

                # Purge expired cooldowns (> 120 seconds)
                expired = [sid for sid, ts in recently_swapped_players.items() if now_ts - ts > 120]
                for sid in expired:
                    del recently_swapped_players[sid]


                # Broadcast announcements for warmup (10s) and active autobalance
                if match_seconds is not None:
                    if match_seconds < 10 and not warmup_10s_sent:
                        try:
                            await rcon_client.broadcast("Modo 50v50: 10s antes de autobalance")
                            warmup_10s_sent = True
                            logger.info("[50v50 Mode] Broadcast sent: 'Modo 50v50: 10s antes de autobalance'")
                        except Exception as err_bc:
                            logger.warning(f"[50v50 Mode] Could not send 10s warmup broadcast: {err_bc}")
                    elif match_seconds >= 10 and not active_broadcast_sent:
                        try:
                            await rcon_client.broadcast("Modo 50v50: Autobalance ACTIVO")
                            active_broadcast_sent = True
                            warmup_10s_sent = True
                            logger.info("[50v50 Mode] Broadcast sent: 'Modo 50v50: Autobalance ACTIVO'")
                        except Exception as err_bc:
                            logger.warning(f"[50v50 Mode] Could not send active broadcast: {err_bc}")

                players_resp = await rcon_client.get_players()
                all_players = players_resp.players or []
                
                blue_players = []
                red_players = []
                green_players = []
                new_entrants = []
                
                # First pass: Categorize existing players vs new entrants
                for p in all_players:
                    f = (p.faction or "").strip().lower()
                    if f.startswith("lone"):
                        blue_players.append(p)
                    elif f.startswith("valk"):
                        f_canonical = "valkyra"
                        if not p.steamId:
                            continue
                        if p.steamId not in player_team_history:
                            new_entrants.append((p, f_canonical))
                        else:
                            hist = player_team_history[p.steamId]
                            bot_swapped = (now_ts - recently_swapped_players.get(p.steamId, 0)) < 15
                            assigned = hist.get("assigned_faction", "valkyra")
                            if not bot_swapped and assigned != "valkyra":
                                # ARMA lock: Revert unauthorized team switch
                                revert_target = green_name
                                logger.warning(f"[50v50 Mode] Player {p.name} ({p.steamId}) attempted manual switch from {assigned} -> valkyra! Reverting...")
                                try:
                                    await rcon_client.switch_faction(p.steamId, revert_target)
                                    recently_swapped_players[p.steamId] = now_ts
                                    await rcon_client.send_player_message(p.steamId, "Cambio de equipo no permitido durante la partida.")
                                except Exception as err_revert:
                                    logger.error(f"[50v50 Mode] Failed to revert {p.steamId}: {err_revert}")
                                green_players.append(p)
                            else:
                                hist["current_faction"] = "valkyra"
                                red_players.append(p)
                    elif f.startswith("mant"):
                        f_canonical = "manticore"
                        if not p.steamId:
                            continue
                        if p.steamId not in player_team_history:
                            new_entrants.append((p, f_canonical))
                        else:
                            hist = player_team_history[p.steamId]
                            bot_swapped = (now_ts - recently_swapped_players.get(p.steamId, 0)) < 15
                            assigned = hist.get("assigned_faction", "manticore")
                            if not bot_swapped and assigned != "manticore":
                                # ARMA lock: Revert unauthorized team switch
                                revert_target = red_name
                                logger.warning(f"[50v50 Mode] Player {p.name} ({p.steamId}) attempted manual switch from {assigned} -> manticore! Reverting...")
                                try:
                                    await rcon_client.switch_faction(p.steamId, revert_target)
                                    recently_swapped_players[p.steamId] = now_ts
                                    await rcon_client.send_player_message(p.steamId, "Cambio de equipo no permitido durante la partida.")
                                except Exception as err_revert:
                                    logger.error(f"[50v50 Mode] Failed to revert {p.steamId}: {err_revert}")
                                red_players.append(p)
                            else:
                                hist["current_faction"] = "manticore"
                                green_players.append(p)
                    else:
                        # Spectator / White / None are strictly ignored
                        continue

                # Step 1: Transfer any players in Lonestar (Blue) to whichever team is smaller
                if blue_players:
                    logger.info(f"[50v50 Mode] Found {len(blue_players)} players in Lonestar (Blue). Transferring... ({red_name}={len(red_players)}, {green_name}={len(green_players)})")
                    for p in blue_players:
                        if not p.steamId:
                            continue
                        existing_hist = player_team_history.get(p.steamId)
                        assigned = existing_hist.get("assigned_faction") if existing_hist else None

                        if assigned == "valkyra" and len(red_players) < 50:
                            target_key = "valkyra"
                            target_faction = red_name
                        elif assigned == "manticore" and len(green_players) < 50:
                            target_key = "manticore"
                            target_faction = green_name
                        elif len(red_players) >= 50 and len(green_players) < 50:
                            target_faction = green_name
                            target_key = "manticore"
                        elif len(green_players) >= 50 and len(red_players) < 50:
                            target_faction = red_name
                            target_key = "valkyra"
                        elif len(red_players) <= len(green_players):
                            target_faction = red_name
                            target_key = "valkyra"
                        else:
                            target_faction = green_name
                            target_key = "manticore"
                            
                        if target_key == "valkyra":
                            red_players.append(p)
                        else:
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

                # Step 2: Process new entrants joining Valkyra or Manticore
                is_warmup = (match_seconds is not None and match_seconds < 10)
                for p, f_canonical in new_entrants:
                    if not p.steamId:
                        continue

                    if f_canonical == "valkyra":
                        chosen_count = len(red_players)
                        opposite_count = len(green_players)
                        target_faction = green_name
                        target_key = "manticore"
                    else:
                        chosen_count = len(green_players)
                        opposite_count = len(red_players)
                        target_faction = red_name
                        target_key = "valkyra"

                    should_redirect = False
                    redirect_reason = ""

                    # Rule 1: Hard-cap of 50 players per team
                    if chosen_count >= 50:
                        should_redirect = True
                        redirect_reason = f"Equipo {f_canonical} lleno (50 jugadores)"
                    elif is_warmup:
                        # Rule 2: Warmup (< 10s) allows freedom up to 6 players difference
                        if (chosen_count - opposite_count) >= 6:
                            should_redirect = True
                            redirect_reason = f"Diferencia máxima superada en calentamiento ({chosen_count} vs {opposite_count})"
                    else:
                        # Rule 3: Post-warmup (>= 10s) Gatekeeper redirects if choosing overpopulated team
                        if chosen_count > opposite_count:
                            should_redirect = True
                            redirect_reason = f"Equipo sobrepoblado ({chosen_count} vs {opposite_count})"

                    if should_redirect and opposite_count < 50:
                        logger.info(f"[50v50 Mode] Gatekeeper: Redirecting {p.name} ({p.steamId}) from {f_canonical} -> {target_faction} [{redirect_reason}]")
                        try:
                            await rcon_client.switch_faction(p.steamId, target_faction)
                            recently_swapped_players[p.steamId] = now_ts
                            player_team_history[p.steamId] = {
                                "current_faction": target_key,
                                "assigned_faction": target_key,
                                "joined_team_at": now_ts,
                            }
                            if target_key == "valkyra":
                                red_players.append(p)
                            else:
                                green_players.append(p)
                            try:
                                await rcon_client.send_player_message(p.steamId, f"Se te ha asignado al equipo {target_faction} para balancear la partida.")
                            except Exception:
                                pass
                        except Exception as err:
                            logger.error(f"[50v50 Mode] Failed to redirect {p.steamId} to {target_faction}: {err}")
                    else:
                        # Entrant accepted into chosen team
                        player_team_history[p.steamId] = {
                            "current_faction": f_canonical,
                            "assigned_faction": f_canonical,
                            "joined_team_at": now_ts,
                        }
                        if f_canonical == "valkyra":
                            red_players.append(p)
                        else:
                            green_players.append(p)
                        logger.info(f"[50v50 Mode] Entrant {p.name} ({p.steamId}) accepted into {f_canonical} (R:{len(red_players)}, G:{len(green_players)})")

                # Step 3: Active Rebalancing (Hard cap of 50 per team & Max 6 difference)
                def get_rebalance_candidates(player_list):
                    valid = [pl for pl in player_list if pl.steamId]
                    # Hierarchical candidate selection:
                    # 1. Protect veterans (cash >= 2000 or kills >= 2) - they are playing/have vehicles
                    # 2. Prefer players not swapped in last 20s (anti-ping-pong)
                    # 3. Lowest cash first
                    # 4. Lowest kills first
                    def candidate_score(pl):
                        cash = pl.cash or 0
                        kills = pl.kills or 0
                        is_veteran = 1 if (cash >= 2000 or kills >= 2) else 0
                        is_recent = 1 if (now_ts - recently_swapped_players.get(pl.steamId, 0)) < 20 else 0
                        return (is_veteran, is_recent, cash, kills)

                    valid.sort(key=candidate_score)
                    return valid


                # 3A. Hard-cap enforcement: strictly enforce max 50 players per team (e.g. 70 vs 30)
                if len(green_players) > 50 and len(red_players) < 50:
                    needed = min(len(green_players) - 50, 50 - len(red_players))
                    candidates = get_rebalance_candidates(green_players)
                    for pl in candidates[:needed]:
                        logger.info(f"[50v50 Mode] Cap Enforcement: Moving {pl.name} ({pl.steamId}) from {green_name} -> {red_name} (Green had {len(green_players)})")
                        try:
                            await rcon_client.switch_faction(pl.steamId, red_name)
                            recently_swapped_players[pl.steamId] = now_ts
                            player_team_history[pl.steamId] = {
                                "current_faction": "valkyra",
                                "assigned_faction": "valkyra",
                                "joined_team_at": now_ts,
                            }
                            red_players.append(pl)
                            if pl in green_players:
                                green_players.remove(pl)
                            try:
                                await rcon_client.send_player_message(pl.steamId, f"Has sido transferido a {red_name} por balance de equipos (límite 50 jugadores).")
                            except Exception:
                                pass
                        except Exception as err:
                            logger.error(f"[50v50 Mode] Failed to cap-balance {pl.steamId}: {err}")

                elif len(red_players) > 50 and len(green_players) < 50:
                    needed = min(len(red_players) - 50, 50 - len(green_players))
                    candidates = get_rebalance_candidates(red_players)
                    for pl in candidates[:needed]:
                        logger.info(f"[50v50 Mode] Cap Enforcement: Moving {pl.name} ({pl.steamId}) from {red_name} -> {green_name} (Red had {len(red_players)})")
                        try:
                            await rcon_client.switch_faction(pl.steamId, green_name)
                            recently_swapped_players[pl.steamId] = now_ts
                            player_team_history[pl.steamId] = {
                                "current_faction": "manticore",
                                "assigned_faction": "manticore",
                                "joined_team_at": now_ts,
                            }
                            green_players.append(pl)
                            if pl in red_players:
                                red_players.remove(pl)
                            try:
                                await rcon_client.send_player_message(pl.steamId, f"Has sido transferido a {green_name} por balance de equipos (límite 50 jugadores).")
                            except Exception:
                                pass
                        except Exception as err:
                            logger.error(f"[50v50 Mode] Failed to cap-balance {pl.steamId}: {err}")

                # 3B. Difference enforcement: max 6 players difference between teams
                diff = len(green_players) - len(red_players)
                if diff > 6 and len(red_players) < 50:
                    transfer_count = min(diff // 2, 50 - len(red_players))
                    candidates = get_rebalance_candidates(green_players)
                    for pl in candidates[:transfer_count]:
                        logger.info(f"[50v50 Mode] Diff Enforcement: Moving {pl.name} ({pl.steamId}) from {green_name} -> {red_name} (Diff was {diff})")
                        try:
                            await rcon_client.switch_faction(pl.steamId, red_name)
                            recently_swapped_players[pl.steamId] = now_ts
                            player_team_history[pl.steamId] = {
                                "current_faction": "valkyra",
                                "assigned_faction": "valkyra",
                                "joined_team_at": now_ts,
                            }
                            red_players.append(pl)
                            if pl in green_players:
                                green_players.remove(pl)
                            try:
                                await rcon_client.send_player_message(pl.steamId, f"Has sido transferido a {red_name} para equilibrar la cantidad de jugadores.")
                            except Exception:
                                pass
                        except Exception as err:
                            logger.error(f"[50v50 Mode] Failed to diff-balance {pl.steamId}: {err}")

                elif diff < -6 and len(green_players) < 50:
                    diff_abs = abs(diff)
                    transfer_count = min(diff_abs // 2, 50 - len(green_players))
                    candidates = get_rebalance_candidates(red_players)
                    for pl in candidates[:transfer_count]:
                        logger.info(f"[50v50 Mode] Diff Enforcement: Moving {pl.name} ({pl.steamId}) from {red_name} -> {green_name} (Diff was {diff_abs})")
                        try:
                            await rcon_client.switch_faction(pl.steamId, green_name)
                            recently_swapped_players[pl.steamId] = now_ts
                            player_team_history[pl.steamId] = {
                                "current_faction": "manticore",
                                "assigned_faction": "manticore",
                                "joined_team_at": now_ts,
                            }
                            green_players.append(pl)
                            if pl in red_players:
                                red_players.remove(pl)
                            try:
                                await rcon_client.send_player_message(pl.steamId, f"Has sido transferido a {green_name} para equilibrar la cantidad de jugadores.")
                            except Exception:
                                pass
                        except Exception as err:
                            logger.error(f"[50v50 Mode] Failed to diff-balance {pl.steamId}: {err}")

        except Exception as e:
            logger.error(f"[50v50 Mode] Error in 50v50 loop: {e}")

        await asyncio.sleep(6)


