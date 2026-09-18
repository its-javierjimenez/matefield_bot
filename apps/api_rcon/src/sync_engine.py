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
    warmup_broadcast_sent = False
    active_broadcast_sent = False
    last_50v50_match_id = None

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
                # Reset tracking on new match transition
                if current_match_id != last_50v50_match_id:
                    logger.info(f"[50v50 Mode] New match detected ({current_match_id}). Resetting team tracking & broadcasts.")
                    last_50v50_match_id = current_match_id
                    player_team_history.clear()
                    recently_swapped_players.clear()
                    warmup_broadcast_sent = False
                    active_broadcast_sent = False

                # Purge expired cooldowns (> 120 seconds)
                expired = [sid for sid, ts in recently_swapped_players.items() if now_ts - ts > 120]
                for sid in expired:
                    del recently_swapped_players[sid]

                # Dynamically resolve exact faction names from live server status (e.g. "Valkyra" vs "Valkyre")
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

                # Broadcast announcements for warmup and active autobalance
                if match_seconds is not None:
                    if match_seconds < 60 and not warmup_broadcast_sent:
                        try:
                            await rcon_client.broadcast("Modo 50v50: 1m antes de autobalance")
                            warmup_broadcast_sent = True
                            logger.info("[50v50 Mode] Broadcast sent: 'Modo 50v50: 1m antes de autobalance'")
                        except Exception as err_bc:
                            logger.warning(f"[50v50 Mode] Could not send warmup broadcast: {err_bc}")
                    elif match_seconds >= 60 and not active_broadcast_sent:
                        try:
                            await rcon_client.broadcast("Modo 50v50: Autobalance ACTIVO")
                            active_broadcast_sent = True
                            warmup_broadcast_sent = True
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
                        if existing_hist and existing_hist.get("assigned_faction") in ("valkyra", "manticore"):
                            target_key = existing_hist["assigned_faction"]
                            target_faction = red_name if target_key == "valkyra" else green_name
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
                is_warmup = (match_seconds is not None and match_seconds < 60)
                for p, f_canonical in new_entrants:
                    if not p.steamId:
                        continue
                    if is_warmup:
                        # 1-minute warmup grace period: Free selection for squads/friends
                        player_team_history[p.steamId] = {
                            "current_faction": f_canonical,
                            "assigned_faction": f_canonical,
                            "joined_team_at": now_ts,
                        }
                        if f_canonical == "valkyra":
                            red_players.append(p)
                        else:
                            green_players.append(p)
                        logger.info(f"[50v50 Mode] Warmup entrant {p.name} ({p.steamId}) joined {f_canonical} (R:{len(red_players)}, G:{len(green_players)})")
                    else:
                        # Post-warmup (matchSeconds >= 60): Overpopulation Gatekeeper
                        # If entrant chooses a team that already has more players than the other, redirect and lock!
                        is_overpopulating = False
                        if f_canonical == "valkyra" and len(red_players) > len(green_players):
                            is_overpopulating = True
                            target_faction = green_name
                            target_key = "manticore"
                        elif f_canonical == "manticore" and len(green_players) > len(red_players):
                            is_overpopulating = True
                            target_faction = red_name
                            target_key = "valkyra"

                        if is_overpopulating:
                            logger.info(f"[50v50 Mode] Overpopulation Gatekeeper: {p.name} ({p.steamId}) tried to join {f_canonical} (R:{len(red_players)} vs G:{len(green_players)}). Redirecting to {target_faction}!")
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
                            # Entrant picked smaller or equal team
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

        except Exception as e:
            logger.error(f"[50v50 Mode] Error in 50v50 loop: {e}")

        await asyncio.sleep(6)


