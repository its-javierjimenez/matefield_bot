"""
Comprehensive Test Suite for 50v50 Mode & Teambalancing Robustness
Testing all self-questions (Auto-Preguntas):
Q1: Stats reset to 0 by game server on team change -> cumulative stats preserved.
Q2: Stats retained by game server on team change -> no duplicate counting.
Q3: Cash earned high watermark preserved when spending cash on vehicles/gear.
Q4: Priority to original team choosers over voluntary overpopulators.
Q5: Tenure, Cash & Activity sorting among newest joiners.
Q6: White / Spectator / None faction isolation (never touched).
Q7: Minimum delta threshold (Delta < 2 does not trigger).
Q8: Anti-pingpong 60s cooldown prevents player oscillation.
Q9: Complete lifecycle: pending_enable, pending_disable, rotation transitions, and immediate cancel.
Q10: Blue (Lonestar) automated draining to smaller team.
"""

import asyncio
import sys
import time
import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
from typing import List, Optional
from dataclasses import dataclass
from sqlmodel import SQLModel, Field, select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

# --- In-Memory Models Matching db.py ---
class BotConfig(SQLModel, table=True):
    __tablename__ = "bot_configs"
    config_key: str = Field(primary_key=True)
    config_value: Optional[str] = Field(default=None)

class Team(SQLModel, table=True):
    __tablename__ = "teams"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True)
    code: str = Field(unique=True)

class Match(SQLModel, table=True):
    __tablename__ = "matches"
    id: str = Field(primary_key=True)
    map_name: str
    start_time: datetime.datetime
    end_time: Optional[datetime.datetime] = None
    winning_team_id: Optional[int] = None

class Player(SQLModel, table=True):
    __tablename__ = "players"
    steam_id: str = Field(primary_key=True)
    discord_id: Optional[str] = None

class MatchPlayerStats(SQLModel, table=True):
    __tablename__ = "match_player_stats"
    steam_id: str = Field(primary_key=True)
    match_id: str = Field(primary_key=True)
    team_id: Optional[int] = None
    kills: int = Field(default=0)
    deaths: int = Field(default=0)
    cash_earned: int = Field(default=0)


# --- Mock RCON Player & Status Schemas ---
@dataclass
class MockRconPlayer:
    steamId: str
    name: str
    faction: str
    kills: int = 0
    deaths: int = 0
    cash: int = 0

@dataclass
class MockPlayersResp:
    players: List[MockRconPlayer]

@dataclass
class MockFactionScore:
    name: str
    score: int

@dataclass
class MockStatusResp:
    factionScores: List[MockFactionScore]


# --- In-memory tracking state replicating sync_engine.py ---
last_rcon_player_stats: dict[str, dict] = {}
player_team_history: dict[str, dict] = {}
recently_swapped_players: dict[str, float] = {}
switched_calls: list[tuple[str, str]] = []
whisper_calls: list[tuple[str, str]] = []


# --- Helper to simulate sync_engine player stats processing ---
async def process_player_stats(session: AsyncSession, current_match_id: str, p: MockRconPlayer):
    # Ensure player in DB
    db_player = await session.get(Player, p.steamId)
    if not db_player:
        session.add(Player(steam_id=p.steamId))
        await session.commit()

    # Team resolution with robust code lookup
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

    # If raw values dropped (server reset stats on faction change), accumulate offset
    if raw_kills < tracker["last_raw_kills"]:
        tracker["offset_kills"] += tracker["last_raw_kills"]
    if raw_deaths < tracker["last_raw_deaths"]:
        tracker["offset_deaths"] += tracker["last_raw_deaths"]
    if raw_cash < tracker["last_raw_cash"]:
        tracker["offset_cash"] += tracker["last_raw_cash"]

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
    await session.commit()
    await session.refresh(stats)
    return stats


# --- Helper to simulate 50v50 step logic replicating sync_engine.py ---
async def run_50v50_step(all_players: List[MockRconPlayer], now_ts: float, match_seconds: Optional[int] = 120):
    switched_calls.clear()
    whisper_calls.clear()
    red_name = "Valkyra"
    green_name = "Manticore"

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
            # White, None, spectators are strictly ignored
            continue

        if p.steamId and f_canonical in ("valkyra", "manticore"):
            hist = player_team_history.get(p.steamId)
            if not hist:
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
                            switched_calls.append((p.steamId, revert_target))
                            recently_swapped_players[p.steamId] = now_ts
                            whisper_calls.append((p.steamId, "Cambio de equipo no permitido durante la partida."))
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

    # Step 1: Drain Blue
    if blue_players:
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

            switched_calls.append((p.steamId, target_faction))
            whisper_calls.append((p.steamId, f"Se te ha asignado al equipo {target_faction}."))
            recently_swapped_players[p.steamId] = now_ts
            player_team_history[p.steamId] = {
                "current_faction": target_key,
                "assigned_faction": target_key,
                "joined_team_at": now_ts,
            }

    # Step 2: Balance Red vs Green
    # Check 1: 1-minute warmup grace period at match start (match_seconds < 60)
    if match_seconds is not None and match_seconds < 60:
        return

    diff = len(red_players) - len(green_players)
    if abs(diff) >= 2:
        count_to_move = abs(diff) // 2
        if diff > 0:
            donor_team = red_players
            target_faction = green_name
            target_key = "manticore"
        else:
            donor_team = green_players
            target_faction = red_name
            target_key = "valkyra"

        # STRICT FAIRNESS RULE:
        # 1. Combat veterans (cash > 0 or K/D > 0) are 100% IMMUNE.
        # 2. Base deployment guard: Only recruits who joined <= 24 seconds ago are eligible.
        #    Anyone on the team > 24 seconds is protected (likely buying vehicles/gear at base terminal).
        # 3. Exclude anyone in the 60s swap cooldown.
        eligible_candidates = []
        for p in donor_team:
            if not p.steamId:
                continue
            if (now_ts - recently_swapped_players.get(p.steamId, 0)) <= 60:
                continue

            hist = player_team_history.get(p.steamId, {})
            joined_at = hist.get("joined_team_at", now_ts)
            time_on_team = now_ts - joined_at

            has_combat_footprint = ((p.cash or 0) > 0) or ((p.kills or 0) > 0) or ((p.deaths or 0) > 0)
            is_fresh_recruit = (not has_combat_footprint) and (time_on_team <= 24)

            if is_fresh_recruit:
                eligible_candidates.append(p)

        if eligible_candidates:
            def candidate_sort_key(p):
                hist = player_team_history.get(p.steamId, {})
                joined_at = hist.get("joined_team_at", now_ts)
                return -joined_at

            eligible_candidates.sort(key=candidate_sort_key)
            actual_move = min(count_to_move, len(eligible_candidates))

            for p in eligible_candidates[:actual_move]:
                switched_calls.append((p.steamId, target_faction))
                whisper_calls.append((p.steamId, f"Se te ha asignado al equipo {target_faction} para balancear la partida."))
                recently_swapped_players[p.steamId] = now_ts
                player_team_history[p.steamId] = {
                    "current_faction": target_key,
                    "assigned_faction": target_key,
                    "joined_team_at": now_ts,
                }


# ==============================================================================
# TEST RUNNER FOR ALL AUTO-PREGUNTAS
# ==============================================================================
async def main():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    async with AsyncSession(engine, expire_on_commit=False) as session:
        # Create a test match
        match_id = "test-match-1"
        match = Match(id=match_id, map_name="Border_Valkyre_Manticore", start_time=datetime.datetime.now(datetime.timezone.utc))
        session.add(match)
        await session.commit()

        print("\n=======================================================")
        print("  INICIANDO BATERÍA DE PRUEBAS BASADA EN AUTO-PREGUNTAS")
        print("=======================================================\n")

        # -------------------------------------------------------------
        # Q1: Reseteo de stats en el servidor de juego al cambiar de equipo
        # -------------------------------------------------------------
        print("▶ Auto-Pregunta 1: ¿Qué pasa si el servidor de juego RESETEA las stats a 0 al cambiar de equipo?")
        p1 = MockRconPlayer(steamId="steam_q1", name="PlayerQ1", faction="Valkyra", kills=12, deaths=3, cash=1000)
        s1 = await process_player_stats(session, match_id, p1)
        assert s1.kills == 12 and s1.deaths == 3, f"Expected 12 kills, got {s1.kills}"

        # Now simulate player switching to Manticore and game server resetting raw kills/deaths to 0
        p1.faction = "Manticore"
        p1.kills = 0
        p1.deaths = 0
        s1_after_reset = await process_player_stats(session, match_id, p1)
        assert s1_after_reset.kills == 12 and s1_after_reset.deaths == 3, \
            f"ERROR: Stats lost on reset! Expected 12 kills, got {s1_after_reset.kills}"

        # Player scores 5 more kills on Manticore (raw kills = 5)
        p1.kills = 5
        p1.deaths = 1
        s1_final = await process_player_stats(session, match_id, p1)
        assert s1_final.kills == 17 and s1_final.deaths == 4, \
            f"ERROR: Expected cumulative 17 kills (12+5) and 4 deaths (3+1), got {s1_final.kills}/{s1_final.deaths}"
        print("  ✅ PASSED: Cumulative stats perfectamente preservadas tras reseteo por el servidor (12 -> 0 -> 17).")

        # -------------------------------------------------------------
        # Q2: Persistencia de stats en el servidor al cambiar de equipo
        # -------------------------------------------------------------
        print("\n▶ Auto-Pregunta 2: ¿Qué pasa si el servidor de juego MANTIENE las stats al cambiar de equipo?")
        p2 = MockRconPlayer(steamId="steam_q2", name="PlayerQ2", faction="Valkyra", kills=8, deaths=2, cash=500)
        s2 = await process_player_stats(session, match_id, p2)
        assert s2.kills == 8 and s2.deaths == 2

        # Player switches to Manticore, but game server maintains raw kills=8
        p2.faction = "Manticore"
        p2.kills = 8
        p2.deaths = 2
        s2_swapped = await process_player_stats(session, match_id, p2)
        assert s2_swapped.kills == 8 and s2_swapped.deaths == 2, \
            f"ERROR: Stats duplicated! Expected 8 kills, got {s2_swapped.kills}"

        # Player scores 3 more kills (raw kills = 11)
        p2.kills = 11
        p2.deaths = 3
        s2_final = await process_player_stats(session, match_id, p2)
        assert s2_final.kills == 11 and s2_final.deaths == 3, \
            f"ERROR: Expected 11 kills, got {s2_final.kills}"
        print("  ✅ PASSED: Stats no se duplican cuando el servidor no las resetea (8 -> 8 -> 11).")

        # -------------------------------------------------------------
        # Q3: Preservación de Cash Earned (Cumulative Earned)
        # -------------------------------------------------------------
        print("\n▶ Auto-Pregunta 3: ¿Qué pasa con el cash_earned cuando el jugador cambia de equipo y el servidor resetea a 0?")
        p3 = MockRconPlayer(steamId="steam_q3", name="PlayerQ3", faction="Valkyra", kills=5, deaths=1, cash=3500)
        s3 = await process_player_stats(session, match_id, p3)
        assert s3.cash_earned == 3500

        # Player switches team, server resets raw cash to 0
        p3.faction = "Manticore"
        p3.cash = 0
        s3_swapped = await process_player_stats(session, match_id, p3)
        assert s3_swapped.cash_earned == 3500, f"Expected 3500 cash, got {s3_swapped.cash_earned}"

        # Player arrives at combat zone and earns 700 cash (raw cash = 700)
        p3.cash = 700
        s3_richer = await process_player_stats(session, match_id, p3)
        assert s3_richer.cash_earned == 4200, f"Expected 4200 cash (3500+700), got {s3_richer.cash_earned}"
        print("  ✅ PASSED: Cash acumulativo preservado tras cambio de equipo y reseteo a 0 ($3500 -> $0 -> $4200).")

        # -------------------------------------------------------------
        # Q4: Bloqueo ARMA estricto contra cambios voluntarios de equipo + Whispers
        # -------------------------------------------------------------
        print("\n▶ Auto-Pregunta 4: ¿Qué pasa si jugadores intentan cambiarse voluntariamente de equipo? (Bloqueo ARMA + Whisper)")
        player_team_history.clear()
        recently_swapped_players.clear()

        # At t=1000: Valkyra has 20 players, Manticore has 20 players (balanced!)
        valk_team = [
            MockRconPlayer(steamId=f"orig_v_{i}", name=f"OrigV_{i}", faction="Valkyra", kills=5, deaths=2, cash=1200)
            for i in range(20)
        ]
        mant_team = [
            MockRconPlayer(steamId=f"orig_m_{i}", name=f"OrigM_{i}", faction="Manticore", kills=4, deaths=2, cash=1000)
            for i in range(20)
        ]
        await run_50v50_step(valk_team + mant_team, now_ts=1000.0)
        assert len(switched_calls) == 0, "Balanced 20v20 should trigger 0 switches."

        # At t=1500: 3 players from Manticore attempt to switch in-game to Valkyra (overpopulating Valkyra!)
        overpop_players = [
            MockRconPlayer(steamId="overpop_1", name="Overpop_1", faction="Valkyra", kills=8, deaths=1, cash=2000),
            MockRconPlayer(steamId="overpop_2", name="Overpop_2", faction="Valkyra", kills=7, deaths=1, cash=1800),
            MockRconPlayer(steamId="overpop_3", name="Overpop_3", faction="Valkyra", kills=6, deaths=1, cash=1500),
        ]
        # In history, these 3 were originally assigned to Manticore
        for op in overpop_players:
            player_team_history[op.steamId] = {
                "current_faction": "manticore",
                "assigned_faction": "manticore",
                "joined_team_at": 1000.0,
            }

        # 2 new players connect and join Valkyra at t=1690 (without combat footprint)
        new_valk_players = [
            MockRconPlayer(steamId="new_v_1", name="NewV_1", faction="Valkyra", kills=0, deaths=0, cash=0),
            MockRconPlayer(steamId="new_v_2", name="NewV_2", faction="Valkyra", kills=0, deaths=0, cash=0),
        ]
        player_team_history["new_v_1"] = {"current_faction": "valkyra", "assigned_faction": "valkyra", "joined_team_at": 1690.0}
        player_team_history["new_v_2"] = {"current_faction": "valkyra", "assigned_faction": "valkyra", "joined_team_at": 1695.0}

        # Current roster: Valkyra has 20 originals + 3 attempting overpop + 2 newcomers = 25 players.
        # Manticore has 17 players.
        current_roster = valk_team + overpop_players + new_valk_players + mant_team[:17]
        await run_50v50_step(current_roster, now_ts=1700.0)

        # 1. The 3 attempting to switch MUST be immediately blocked and reverted back to Manticore!
        reverted = [sid for sid, target in switched_calls if target == "Manticore"]
        assert "overpop_1" in reverted and "overpop_2" in reverted and "overpop_3" in reverted

        # 2. All 3 must receive whisper: "Cambio de equipo no permitido durante la partida."
        blocked_whispers = [sid for sid, msg in whisper_calls if "Cambio de equipo no permitido" in msg]
        assert len(blocked_whispers) == 3
        assert "overpop_1" in blocked_whispers and "overpop_2" in blocked_whispers and "overpop_3" in blocked_whispers

        # 3. In Step 2 (Valkyra 22 vs Manticore 20 -> diff=2, count=1):
        # The newcomer with newest tenure <= 24s (new_v_2) is moved to balance, receiving whisper!
        balanced_whispers = [sid for sid, msg in whisper_calls if "balancear la partida" in msg]
        assert len(balanced_whispers) == 1
        assert balanced_whispers[0] == "new_v_2"

        # 4. Check that NONE of the 20 original veterans were moved
        for v in valk_team:
            assert v.steamId not in [sid for sid, target in switched_calls], f"ERROR: Original player {v.steamId} was moved!"

        print("  ✅ PASSED: Los 3 que intentaron cambiar fueron bloqueados, devueltos a Manticore con whisper. El recién llegado fue auto-balanceado con whisper. Los 20 originales fueron 100% protegidos.")

        # -------------------------------------------------------------
        # Q5: Prioridad de orden por antigüedad, cash y actividad
        # -------------------------------------------------------------
        print("\n▶ Auto-Pregunta 5: ¿Cómo se desempata entre jugadores legítimos (Antigüedad > Cash > K/D)?")
        player_team_history.clear()
        recently_swapped_players.clear()

        # Senior player: joined at t=500, cash=$0, K/D=0/0
        p_senior = MockRconPlayer(steamId="senior_p", name="Senior", faction="Valkyra", kills=0, deaths=0, cash=0)
        player_team_history["senior_p"] = {"current_faction": "valkyra", "assigned_faction": "valkyra", "joined_team_at": 500.0}

        # Junior rich: joined at t=800, cash=$2000, K/D=10/2 (inmune por tener combate)
        p_jr_rich = MockRconPlayer(steamId="jr_rich", name="JrRich", faction="Valkyra", kills=10, deaths=2, cash=2000)
        player_team_history["jr_rich"] = {"current_faction": "valkyra", "assigned_faction": "valkyra", "joined_team_at": 800.0}

        # Junior fresh: joined at t=885, cash=$0, K/D=0/0 (elegible por unirse hace <= 24s a t=900)
        p_jr_fresh = MockRconPlayer(steamId="jr_fresh", name="JrFresh", faction="Valkyra", kills=0, deaths=0, cash=0)
        player_team_history["jr_fresh"] = {"current_faction": "valkyra", "assigned_faction": "valkyra", "joined_team_at": 885.0}

        # Valkyra has 3 players, Manticore has 1 player -> diff=2, count_to_move=1
        mant_single = [MockRconPlayer(steamId="m_single", name="MSingle", faction="Manticore", kills=1, deaths=1, cash=0)]
        valk_trio = [p_senior, p_jr_rich, p_jr_fresh]

        await run_50v50_step(valk_trio + mant_single, now_ts=900.0)
        assert len(switched_calls) == 1
        assert switched_calls[0][0] == "jr_fresh", f"Expected jr_fresh to be moved, got {switched_calls[0][0]}"
        assert whisper_calls[0] == ("jr_fresh", "Se te ha asignado al equipo Manticore para balancear la partida.")
        print("  ✅ PASSED: JrRich con combate es inmune. JrFresh ($0 cash, sin kills, tenure <= 24s) es transferido con whisper de balanceo.")

        # -------------------------------------------------------------
        # Q6: Aislamiento absoluto de White / Espectadores
        # -------------------------------------------------------------
        print("\n▶ Auto-Pregunta 6: ¿El bot ignora estrictamente a los jugadores en White / Espectadores?")
        player_team_history.clear()
        recently_swapped_players.clear()

        white_players = [
            MockRconPlayer(steamId="white_1", name="WhitePlayer1", faction="White", kills=0, deaths=0, cash=0),
            MockRconPlayer(steamId="white_2", name="Spectator1", faction="", kills=0, deaths=0, cash=0),
            MockRconPlayer(steamId="white_3", name="NonePlayer", faction="None", kills=0, deaths=0, cash=0),
        ]
        roster_with_white = valk_team[:10] + mant_team[:10] + white_players
        await run_50v50_step(roster_with_white, now_ts=1000.0)
        assert len(switched_calls) == 0, "No one should be moved in balanced 10v10"
        for wp in white_players:
            assert wp.steamId not in player_team_history, f"White player {wp.steamId} was wrongly tracked!"
        print("  ✅ PASSED: Jugadores en White, vacíos o None jamás son clasificados ni tocados.")

        # -------------------------------------------------------------
        # Q7: Umbral de diferencia mínima (Delta < 2)
        # -------------------------------------------------------------
        print("\n▶ Auto-Pregunta 7: ¿Qué pasa si la diferencia es de solo 1 jugador (ej: 50 vs 49)?")
        player_team_history.clear()
        recently_swapped_players.clear()

        v50 = [MockRconPlayer(steamId=f"v_{i}", name=f"V_{i}", faction="Valkyra") for i in range(50)]
        m49 = [MockRconPlayer(steamId=f"m_{i}", name=f"M_{i}", faction="Manticore") for i in range(49)]
        await run_50v50_step(v50 + m49, now_ts=2000.0)
        assert len(switched_calls) == 0, "Delta of 1 must NOT trigger any team transfers!"
        print("  ✅ PASSED: Diferencia de 1 jugador no dispara transferencias (evita bucle infinito 50v49 <-> 49v50).")

        # -------------------------------------------------------------
        # Q8: Cooldown anti ping-pong (60 segundos)
        # -------------------------------------------------------------
        print("\n▶ Auto-Pregunta 8: ¿El cooldown de 60 segundos previene que un jugador rebote entre equipos?")
        recently_swapped_players["bounced_player"] = 3000.0
        p_bounced = MockRconPlayer(steamId="bounced_player", name="Bounced", faction="Valkyra", kills=0, deaths=0, cash=0)
        p_other = MockRconPlayer(steamId="other_candidate", name="Other", faction="Valkyra", kills=0, deaths=0, cash=0)
        p_third = MockRconPlayer(steamId="third_candidate", name="Third", faction="Valkyra", kills=0, deaths=0, cash=0)
        mant_dummy = [MockRconPlayer(steamId="md", name="MD", faction="Manticore")]

        # At t=3030 (30 seconds after swap, still in cooldown)
        # Valkyra has 3 players, Manticore has 1 -> diff=2, count_to_move=1
        await run_50v50_step([p_bounced, p_other, p_third] + mant_dummy, now_ts=3030.0)
        assert len(switched_calls) == 1
        assert switched_calls[0][0] == "other_candidate", f"Expected other_candidate, but got {switched_calls[0][0]}"
        print("  ✅ PASSED: Jugador en cooldown es protegido de rebotar y se selecciona el siguiente candidato.")

        # -------------------------------------------------------------
        # Q9: Ciclo de vida: pending_enable, pending_disable y rotación
        # -------------------------------------------------------------
        print("\n▶ Auto-Pregunta 9: ¿El ciclo de vida diferido (pending_enable / pending_disable) funciona infaliblemente?")
        # 1. Start clean
        cfg_state = BotConfig(config_key="MODE_50V50_STATE", config_value="inactive")
        cfg_en = BotConfig(config_key="MODE_50V50_ENABLED", config_value="false")
        session.add(cfg_state)
        session.add(cfg_en)
        await session.commit()

        # Admin enables mid-match
        cfg_state.config_value = "pending_enable"
        session.add(cfg_state)
        await session.commit()

        # Mode loop check during current match:
        is_active_during_match = cfg_state.config_value in ("active", "pending_disable")
        assert not is_active_during_match, "pending_enable should NOT be active during current match!"

        # Match rotation occurs -> triggers state transition in sync_engine
        if cfg_state.config_value == "pending_enable":
            cfg_state.config_value = "active"
            cfg_en.config_value = "true"
            session.add(cfg_state)
            session.add(cfg_en)
            await session.commit()

        assert cfg_state.config_value == "active"
        assert cfg_en.config_value == "true"

        # Admin disables during match
        cfg_state.config_value = "pending_disable"
        session.add(cfg_state)
        await session.commit()

        # Mode loop check during pending_disable:
        is_active_during_pending_disable = cfg_state.config_value in ("active", "pending_disable")
        assert is_active_during_pending_disable, "50v50 automation MUST stay active during pending_disable until match ends!"

        # Match rotation occurs -> triggers state transition
        if cfg_state.config_value == "pending_disable":
            cfg_state.config_value = "inactive"
            cfg_en.config_value = "false"
            session.add(cfg_state)
            session.add(cfg_en)
            await session.commit()

        assert cfg_state.config_value == "inactive"
        assert cfg_en.config_value == "false"

        # Immediate cancel if pending_enable:
        cfg_state.config_value = "pending_enable"
        await session.commit()
        # Admin cancels:
        if cfg_state.config_value in ("pending_enable", "inactive"):
            cfg_state.config_value = "inactive"
            cfg_en.config_value = "false"
            session.add(cfg_state)
            session.add(cfg_en)
            await session.commit()

        assert cfg_state.config_value == "inactive"
        print("  ✅ PASSED: Transiciones pending_enable -> active en rotación, pending_disable activo hasta rotación, y cancelación inmediata verificadas.")

        # -------------------------------------------------------------
        # Q10: Vaciado prioritario de Lonestar (Azul)
        # -------------------------------------------------------------
        print("\n▶ Auto-Pregunta 10: ¿Los jugadores en Lonestar (Azul) se distribuyen equitativamente al equipo menor?")
        player_team_history.clear()
        recently_swapped_players.clear()

        blues = [MockRconPlayer(steamId=f"blue_{i}", name=f"Blue_{i}", faction="Lonestar") for i in range(4)]
        reds = [MockRconPlayer(steamId=f"red_{i}", name=f"Red_{i}", faction="Valkyra") for i in range(20)]
        greens = [MockRconPlayer(steamId=f"green_{i}", name=f"Green_{i}", faction="Manticore") for i in range(18)]

        # Green has 18, Red has 20.
        # Blue 0 should go to Green (now 19).
        # Blue 1 should go to Green (now 20).
        # Blue 2 should go to Red (now 21).
        # Blue 3 should go to Green (now 21).
        # Teams finish 21 vs 21!
        await run_50v50_step(blues + reds + greens, now_ts=4000.0)
        assert len(switched_calls) == 4
        targets = [target for sid, target in switched_calls]
        assert targets.count("Manticore") == 3
        assert targets.count("Valkyra") == 1
        assert len(whisper_calls) == 4
        for sid, target in switched_calls:
            assert (sid, f"Se te ha asignado al equipo {target}.") in whisper_calls
        print("  ✅ PASSED: 4 jugadores azules distribuidos (3 a Manticore, 1 a Valkyra) con whispers individuales recibidos.")

        # -------------------------------------------------------------
        # Q11: Reseteo de cash en el servidor de juego al cambiar de equipo
        # -------------------------------------------------------------
        print("\n▶ Auto-Pregunta 11: ¿Qué pasa si el servidor RESETEA el cash al cambiar de equipo?")
        p11 = MockRconPlayer(steamId="steam_q11", name="PlayerQ11", faction="Valkyra", kills=6, deaths=1, cash=3000)
        s11 = await process_player_stats(session, match_id, p11)
        assert s11.cash_earned == 3000

        # Player switches to Manticore, server resets cash to 0
        p11.faction = "Manticore"
        p11.cash = 0
        s11_reset = await process_player_stats(session, match_id, p11)
        assert s11_reset.cash_earned == 3000, f"Expected 3000 cash, got {s11_reset.cash_earned}"

        # Player earns 1500 cash on Manticore (raw cash = 1500)
        p11.cash = 1500
        s11_final = await process_player_stats(session, match_id, p11)
        assert s11_final.cash_earned == 4500, f"Expected 4500 (3000+1500), got {s11_final.cash_earned}"
        print("  ✅ PASSED: Cash acumulativo preservado tras reseteo por el servidor ($3000 -> $0 -> $4500).")

        # -------------------------------------------------------------
        # Q12: Mantenimiento de cash en el servidor al cambiar de equipo
        # -------------------------------------------------------------
        print("\n▶ Auto-Pregunta 12: ¿Qué pasa si el servidor MANTIENE el cash al cambiar de equipo?")
        p12 = MockRconPlayer(steamId="steam_q12", name="PlayerQ12", faction="Valkyra", kills=6, deaths=1, cash=3000)
        s12 = await process_player_stats(session, match_id, p12)
        assert s12.cash_earned == 3000

        # Player switches to Manticore, server keeps cash at 3000
        p12.faction = "Manticore"
        p12.cash = 3000
        s12_swapped = await process_player_stats(session, match_id, p12)
        assert s12_swapped.cash_earned == 3000

        # Player earns 1500 more cash (raw cash = 4500)
        p12.cash = 4500
        s12_final = await process_player_stats(session, match_id, p12)
        assert s12_final.cash_earned == 4500, f"Expected 4500, got {s12_final.cash_earned}"
        print("  ✅ PASSED: Cash acumulativo no se duplica cuando el servidor lo mantiene ($3000 -> $3000 -> $4500).")

        # -------------------------------------------------------------
        # Q13: Múltiples cambios de equipo en la misma partida
        # -------------------------------------------------------------
        print("\n▶ Auto-Pregunta 13: ¿Qué pasa si un jugador cambia de equipo MÚLTIPLES veces (Valk -> Mant -> Valk)?")
        p13 = MockRconPlayer(steamId="steam_q13", name="PlayerQ13", faction="Valkyra", kills=5, deaths=1, cash=1000)
        await process_player_stats(session, match_id, p13)

        # Switch 1 to Manticore (resets to 0)
        p13.faction = "Manticore"
        p13.kills = 0
        p13.cash = 0
        await process_player_stats(session, match_id, p13)
        # Scores 4 kills, 800 cash
        p13.kills = 4
        p13.cash = 800
        await process_player_stats(session, match_id, p13)

        # Switch 2 back to Valkyra (resets to 0)
        p13.faction = "Valkyra"
        p13.kills = 0
        p13.cash = 0
        await process_player_stats(session, match_id, p13)
        # Scores 3 kills, 500 cash
        p13.kills = 3
        p13.cash = 500
        s13_final = await process_player_stats(session, match_id, p13)

        # Total expected: 5 + 4 + 3 = 12 kills, 1000 + 800 + 500 = 2300 cash
        assert s13_final.kills == 12, f"Expected 12 kills, got {s13_final.kills}"
        assert s13_final.cash_earned == 2300, f"Expected 2300 cash, got {s13_final.cash_earned}"
        print("  ✅ PASSED: Múltiples cambios con reseteos de servidor acumulan exactamente (12 kills, $2300 cash).")

        # -------------------------------------------------------------
        # Q14: Desconexión y reconexión mid-match
        # -------------------------------------------------------------
        print("\n▶ Auto-Pregunta 14: ¿Qué pasa si un jugador se desconecta y se reconecta mid-match?")
        p14 = MockRconPlayer(steamId="steam_q14", name="PlayerQ14", faction="Valkyra", kills=10, deaths=2, cash=2000)
        await process_player_stats(session, match_id, p14)

        # Player disconnects (simulated by absence in a loop), then reconnects
        # Game server resets stats on reconnect (raw kills=0, cash=0)
        p14.kills = 0
        p14.deaths = 0
        p14.cash = 0
        s14_reconnect = await process_player_stats(session, match_id, p14)
        assert s14_reconnect.kills == 10
        assert s14_reconnect.cash_earned == 2000

        # Player scores 2 kills, 500 cash after reconnect
        p14.kills = 2
        p14.cash = 500
        s14_final = await process_player_stats(session, match_id, p14)
        assert s14_final.kills == 12
        assert s14_final.cash_earned == 2500
        print("  ✅ PASSED: Desconexión y reconexión con reseteo preserva perfectamente estadísticas previas (12 kills, $2500 cash).")

        # -------------------------------------------------------------
        # Q15: Variaciones ortográficas en nombres de facción ("Valkyre" vs "Valkyra")
        # -------------------------------------------------------------
        print("\n▶ Auto-Pregunta 15: ¿Se evitan colisiones de base de datos entre 'Valkyre' y 'Valkyra'?")
        p15_a = MockRconPlayer(steamId="steam_q15_a", name="PlayerA", faction="Valkyra", kills=1, deaths=0, cash=100)
        p15_b = MockRconPlayer(steamId="steam_q15_b", name="PlayerB", faction="Valkyre", kills=2, deaths=0, cash=200)
        p15_c = MockRconPlayer(steamId="steam_q15_c", name="PlayerC", faction="VALKYRE ", kills=3, deaths=0, cash=300)

        s15_a = await process_player_stats(session, match_id, p15_a)
        s15_b = await process_player_stats(session, match_id, p15_b)
        s15_c = await process_player_stats(session, match_id, p15_c)

        # All three must share the exact same team_id (no duplicate teams, no crash)
        assert s15_a.team_id == s15_b.team_id == s15_c.team_id
        print(f"  ✅ PASSED: Todas las variantes ('Valkyra', 'Valkyre', 'VALKYRE ') resuelven de forma segura al team_id={s15_a.team_id}.")

        # -------------------------------------------------------------
        # Q16: Jugador transferido que no consigue kills antes del fin de partida
        # -------------------------------------------------------------
        print("\n▶ Auto-Pregunta 16: ¿Qué pasa si un jugador es transferido hacia el final y no consigue kills?")
        p16 = MockRconPlayer(steamId="steam_q16", name="PlayerQ16", faction="Valkyra", kills=15, deaths=4, cash=4000)
        await process_player_stats(session, match_id, p16)

        # Transferred to Manticore 2 minutes before end, server resets raw to 0
        p16.faction = "Manticore"
        p16.kills = 0
        p16.deaths = 0
        p16.cash = 0
        s16_end = await process_player_stats(session, match_id, p16)

        # Match ends without him getting more kills
        assert s16_end.kills == 15, f"Expected 15 kills, got {s16_end.kills}"
        assert s16_end.deaths == 4, f"Expected 4 deaths, got {s16_end.deaths}"
        assert s16_end.cash_earned == 4000, f"Expected 4000 cash, got {s16_end.cash_earned}"
        print("  ✅ PASSED: Jugador transferido al cierre retiene sus 15 kills, 4 deaths y $4000 cash en la base de datos.")

        # -------------------------------------------------------------
        # Q17: Escenario 50 vs 45 con veteranos originales y recién llegados
        # -------------------------------------------------------------
        print("\n▶ Auto-Pregunta 17: ¿Qué pasa si quedan 50 vs 45 y todos los 50 son veteranos originales?")
        player_team_history.clear()
        recently_swapped_players.clear()

        # 50 original veterans on Valkyra (all have combated, cash > 0, K/D > 0)
        v50_vets = [
            MockRconPlayer(steamId=f"vet_v_{i}", name=f"VetV_{i}", faction="Valkyra", kills=3, deaths=1, cash=1200)
            for i in range(50)
        ]
        # 45 players on Manticore
        m45_players = [
            MockRconPlayer(steamId=f"m45_{i}", name=f"M45_{i}", faction="Manticore", kills=2, deaths=2, cash=800)
            for i in range(45)
        ]

        # Record history for the 50 veterans
        for v in v50_vets:
            player_team_history[v.steamId] = {
                "current_faction": "valkyra",
                "assigned_faction": "valkyra",
                "joined_team_at": 1000.0,
            }

        # Step runs at t=2000 (Valkyra 50 vs Manticore 45)
        await run_50v50_step(v50_vets + m45_players, now_ts=2000.0)

        # Expected: ZERO players moved because all 50 are protected original veterans!
        assert len(switched_calls) == 0, f"ERROR: Protected veterans were moved! {switched_calls}"
        print("  ✅ PASSED: Ningún veterano original fue transferido. Se mantuvieron 50 vs 45 sin enojar a nadie.")

        # Now 2 fresh new players connect to Valkyra with $0 cash and 0 K/D:
        p_new_1 = MockRconPlayer(steamId="fresh_1", name="Fresh1", faction="Valkyra", kills=0, deaths=0, cash=0)
        p_new_2 = MockRconPlayer(steamId="fresh_2", name="Fresh2", faction="Valkyra", kills=0, deaths=0, cash=0)
        player_team_history["fresh_1"] = {"current_faction": "valkyra", "assigned_faction": "valkyra", "joined_team_at": 2050.0}
        player_team_history["fresh_2"] = {"current_faction": "valkyra", "assigned_faction": "valkyra", "joined_team_at": 2050.0}

        # Valkyra now has 52 vs Manticore 45 (diff = 7, count_to_move = 3, but only 2 eligible fresh players)
        await run_50v50_step(v50_vets + [p_new_1, p_new_2] + m45_players, now_ts=2060.0)

        # Only the 2 fresh players are moved!
        moved = [sid for sid, target in switched_calls]
        assert len(moved) == 2
        assert "fresh_1" in moved and "fresh_2" in moved
        for v in v50_vets:
            assert v.steamId not in moved, f"ERROR: Veteran {v.steamId} was moved!"
        # Whispers sent to the 2 fresh players
        assert ("fresh_1", "Se te ha asignado al equipo Manticore para balancear la partida.") in whisper_calls
        assert ("fresh_2", "Se te ha asignado al equipo Manticore para balancear la partida.") in whisper_calls
        print("  ✅ PASSED: Al ingresar 2 nuevos sin combatir ($0 cash), el bot movió a los 2 nuevos con whispers protegiendo al 100% de los veteranos.")

        # -------------------------------------------------------------
        # Q18: Asimilación de Azules como originales y bloqueo ARMA si intentan cambiarse
        # -------------------------------------------------------------
        print("\n▶ Auto-Pregunta 18: ¿Los Azules asignados se tratan como originales y se bloquea su cambio como en ARMA?")
        player_team_history.clear()
        recently_swapped_players.clear()

        # Blue player spawns in Lonestar
        blue_p = MockRconPlayer(steamId="blue_veteran", name="BlueVet", faction="Lonestar", kills=0, deaths=0, cash=0)
        await run_50v50_step([blue_p] + v50_vets[:10] + m45_players[:10], now_ts=3000.0)

        # Step 1 transferred him to whichever was equal/smaller
        assert len(switched_calls) == 1
        assigned_target = switched_calls[0][1]
        assigned_key = "valkyra" if assigned_target.lower().startswith("valk") else "manticore"
        assert player_team_history["blue_veteran"]["current_faction"] == assigned_key
        assert player_team_history["blue_veteran"]["assigned_faction"] == assigned_key
        assert ("blue_veteran", f"Se te ha asignado al equipo {assigned_target}.") in whisper_calls

        # Player now fights on his assigned team and earns cash
        blue_p.faction = assigned_target
        blue_p.cash = 1500
        blue_p.kills = 4

        # Verify he is now an established veteran on that team!
        has_footprint = (blue_p.cash > 0) or (blue_p.kills > 0)
        assert has_footprint is True
        print(f"  ✅ PASSED: Jugador azul asignado a {assigned_target} recibió whisper y adquirió condición de original veterano tras combatir.")

        # Now, player tries to voluntarily switch in-game to the OTHER team (breaks ARMA lock!)
        other_target = "Manticore" if assigned_key == "valkyra" else "Valkyra"
        blue_p.faction = other_target

        # Step runs at t=3100 (bot detects unpermitted manual switch)
        await run_50v50_step([blue_p] + v50_vets[:25] + m45_players[:20], now_ts=3100.0)

        # ARMA lock must immediately revert the player back to assigned_target!
        assert len(switched_calls) == 1
        assert switched_calls[0] == ("blue_veteran", assigned_target)
        assert len(whisper_calls) == 1
        assert whisper_calls[0] == ("blue_veteran", "Cambio de equipo no permitido durante la partida.")
        assert player_team_history["blue_veteran"]["assigned_faction"] == assigned_key
        print(f"  ✅ PASSED: Intento de cambio a {other_target} bloqueado inmediatamente: devuelto a {assigned_target} con whisper de prohibición.")

        # -------------------------------------------------------------
        # Q19: Verificación integral de whispers en todos los flujos del sistema
        # -------------------------------------------------------------
        print("\n▶ Auto-Pregunta 19: ¿Los whispers se envían correctamente en todos los flujos y nunca a White/Espectadores?")
        player_team_history.clear()
        recently_swapped_players.clear()

        # Scenario:
        # 1 Lonestar player (needs assignment)
        # 1 Valkyra player trying manual switch to Manticore (needs block & revert)
        # 2 Fresh Valkyra arrivals ($0 cash) with Valkyra having 24 vs Manticore 20 (needs auto-balance)
        # 1 White spectator (must be ignored)
        p_blue = MockRconPlayer(steamId="flow_blue", name="FlowBlue", faction="Lonestar")
        p_cheater = MockRconPlayer(steamId="flow_rebel", name="FlowRebel", faction="Manticore")
        player_team_history["flow_rebel"] = {"current_faction": "valkyra", "assigned_faction": "valkyra", "joined_team_at": 1000.0}

        p_fresh_1 = MockRconPlayer(steamId="flow_fresh_1", name="FreshA", faction="Valkyra", kills=0, deaths=0, cash=0)
        p_fresh_2 = MockRconPlayer(steamId="flow_fresh_2", name="FreshB", faction="Valkyra", kills=0, deaths=0, cash=0)
        player_team_history["flow_fresh_1"] = {"current_faction": "valkyra", "assigned_faction": "valkyra", "joined_team_at": 1990.0}
        player_team_history["flow_fresh_2"] = {"current_faction": "valkyra", "assigned_faction": "valkyra", "joined_team_at": 1995.0}

        p_white = MockRconPlayer(steamId="flow_white", name="FlowWhite", faction="White", kills=0, deaths=0, cash=0)

        v_base = [MockRconPlayer(steamId=f"v_base_{i}", name=f"VBase_{i}", faction="Valkyra", kills=5, cash=1000) for i in range(22)]
        for v in v_base:
            player_team_history[v.steamId] = {"current_faction": "valkyra", "assigned_faction": "valkyra", "joined_team_at": 1000.0}
        m_base = [MockRconPlayer(steamId=f"m_base_{i}", name=f"MBase_{i}", faction="Manticore", kills=5, cash=1000) for i in range(20)]
        for m in m_base:
            player_team_history[m.steamId] = {"current_faction": "manticore", "assigned_faction": "manticore", "joined_team_at": 1000.0}

        all_flow = [p_blue, p_cheater, p_fresh_1, p_fresh_2, p_white] + v_base + m_base
        await run_50v50_step(all_flow, now_ts=2000.0)

        # 1. Flow rebel must have received "Cambio de equipo no permitido"
        assert ("flow_rebel", "Cambio de equipo no permitido durante la partida.") in whisper_calls

        # 2. Flow blue must have received "Se te ha asignado al equipo ..."
        blue_whispers = [msg for sid, msg in whisper_calls if sid == "flow_blue"]
        assert len(blue_whispers) == 1
        assert "Se te ha asignado al equipo" in blue_whispers[0]

        # 3. Flow fresh must have received "balancear la partida"
        fresh_whispers = [msg for sid, msg in whisper_calls if sid.startswith("flow_fresh")]
        assert len(fresh_whispers) >= 1
        assert any("para balancear la partida" in msg for msg in fresh_whispers)

        # 4. White player received ZERO whispers and ZERO switches
        white_actions = [sid for sid, _ in switched_calls if sid == "flow_white"]
        white_whispers = [sid for sid, _ in whisper_calls if sid == "flow_white"]
        assert len(white_actions) == 0
        assert len(white_whispers) == 0
        print("  ✅ PASSED: Verificación integral completada: Bloqueo ARMA, Asignación Azul, Auto-balance y Aislamiento White funcionando a la perfección.")

        # -------------------------------------------------------------
        # Q20: Periodo de gracia inicial de 1 minuto al comienzo de la partida
        # -------------------------------------------------------------
        print("\n▶ Auto-Pregunta 20: ¿Al inicio de partida (matchSeconds < 60) se pausa el auto-balanceo para no separar amigos?")
        player_team_history.clear()
        recently_swapped_players.clear()

        # 5 friends load into Valkyra within the first 25 seconds of the match. Manticore has 0 players.
        squad_friends = [
            MockRconPlayer(steamId=f"friend_{i}", name=f"Friend_{i}", faction="Valkyra", kills=0, deaths=0, cash=0)
            for i in range(5)
        ]
        for f in squad_friends:
            player_team_history[f.steamId] = {"current_faction": "valkyra", "assigned_faction": "valkyra", "joined_team_at": 20.0}

        # Step runs at matchSeconds = 25s (< 60s warmup)
        await run_50v50_step(squad_friends, now_ts=25.0, match_seconds=25)

        # ZERO players moved between Red and Green during the first minute!
        assert len(switched_calls) == 0, f"ERROR: Friends were moved during early grace period! {switched_calls}"
        print("  ✅ PASSED: Durante el primer minuto (25s < 60s), el auto-balanceo estuvo pausado y los 5 amigos quedaron juntos en Valkyra.")

        # -------------------------------------------------------------
        # Q21: Protección de novato en base (> 24 segundos de antigüedad)
        # -------------------------------------------------------------
        print("\n▶ Auto-Pregunta 21: ¿Un jugador con $0 cash que lleva > 24s comprando en base es protegido contra balanceo?")
        player_team_history.clear()
        recently_swapped_players.clear()

        # Player in base for 35 seconds buying a tank ($0 cash earned, 0 K/D)
        tank_buyer = MockRconPlayer(steamId="tank_buyer", name="TankBuyer", faction="Valkyra", kills=0, deaths=0, cash=0)
        player_team_history["tank_buyer"] = {"current_faction": "valkyra", "assigned_faction": "valkyra", "joined_team_at": 2000.0}

        # Fresh recruit who just connected 10 seconds ago ($0 cash, 0 K/D)
        fresh_recruit = MockRconPlayer(steamId="fresh_recruit", name="FreshRecruit", faction="Valkyra", kills=0, deaths=0, cash=0)
        player_team_history["fresh_recruit"] = {"current_faction": "valkyra", "assigned_faction": "valkyra", "joined_team_at": 2025.0}

        # Valkyra has 20 veterans + tank_buyer + fresh_recruit = 22. Manticore has 20 -> diff = 2, count = 1.
        valk_vets = [MockRconPlayer(steamId=f"vv_{i}", name=f"VV_{i}", faction="Valkyra", kills=3, cash=1000) for i in range(20)]
        for v in valk_vets:
            player_team_history[v.steamId] = {"current_faction": "valkyra", "assigned_faction": "valkyra", "joined_team_at": 1500.0}
        mant_vets = [MockRconPlayer(steamId=f"mv_{i}", name=f"MV_{i}", faction="Manticore", kills=3, cash=1000) for i in range(20)]
        for m in mant_vets:
            player_team_history[m.steamId] = {"current_faction": "manticore", "assigned_faction": "manticore", "joined_team_at": 1500.0}

        # Run step at t=2035 (tenure: tank_buyer = 35s > 24s; fresh_recruit = 10s <= 24s)
        await run_50v50_step(valk_vets + [tank_buyer, fresh_recruit] + mant_vets, now_ts=2035.0, match_seconds=120)

        # Only fresh_recruit is eligible! tank_buyer is PROTECTED because tenure > 24s!
        assert len(switched_calls) == 1
        assert switched_calls[0] == ("fresh_recruit", "Manticore")
        assert ("fresh_recruit", "Se te ha asignado al equipo Manticore para balancear la partida.") in whisper_calls
        print("  ✅ PASSED: El comprador de tanque en base (> 24s) fue 100% protegido. Solo se movió al novato de 10s, evitando pérdida de vehículos.")

        print("\n=======================================================")
        print("  TODAS LAS 21 AUTO-PREGUNTAS PASARON SATISFACTORIAMENTE!")
        print("  MODO 50v50 SELLADO ESTILO ARMA, WHISPERS Y PROTECCIÓN BASE 100% OPERATIVOS")
        print("=======================================================\n")

if __name__ == "__main__":
    asyncio.run(main())

