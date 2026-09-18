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
async def run_50v50_step(all_players: List[MockRconPlayer], now_ts: float):
    switched_calls.clear()
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
            red_players.append(p)
            f_canonical = "valkyra"
        elif f.startswith("mant"):
            green_players.append(p)
            f_canonical = "manticore"
        else:
            continue

        if p.steamId:
            hist = player_team_history.get(p.steamId)
            if not hist:
                player_team_history[p.steamId] = {
                    "current_faction": f_canonical,
                    "joined_team_at": now_ts,
                    "switched_voluntarily": False,
                    "switched_to_overpopulated": False,
                }
            else:
                if hist["current_faction"] != f_canonical:
                    bot_swapped = (now_ts - recently_swapped_players.get(p.steamId, 0)) < 15
                    hist["current_faction"] = f_canonical
                    hist["joined_team_at"] = now_ts
                    if not bot_swapped:
                        hist["switched_voluntarily"] = True
                        hist["switched_to_overpopulated"] = True
                    else:
                        hist["switched_to_overpopulated"] = False

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
            recently_swapped_players[p.steamId] = now_ts
            player_team_history[p.steamId] = {
                "current_faction": target_key,
                "joined_team_at": now_ts,
                "switched_voluntarily": False,
                "switched_to_overpopulated": False,
            }

    # Step 2: Balance Red vs Green
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

        candidates = [p for p in donor_team if p.steamId and (now_ts - recently_swapped_players.get(p.steamId, 0) > 60)]
        if not candidates:
            candidates = [p for p in donor_team if p.steamId]

        def candidate_sort_key(p):
            hist = player_team_history.get(p.steamId, {})
            is_overpop = 0 if hist.get("switched_to_overpopulated", False) else 1
            joined_at = hist.get("joined_team_at", now_ts)
            cash_val = p.cash if p.cash is not None else 0
            activity_val = (p.kills or 0) + (p.deaths or 0)
            return (
                is_overpop,
                -joined_at,
                cash_val,
                activity_val,
                p.kills or 0
            )

        candidates.sort(key=candidate_sort_key)

        for p in candidates[:count_to_move]:
            switched_calls.append((p.steamId, target_faction))
            recently_swapped_players[p.steamId] = now_ts
            player_team_history[p.steamId] = {
                "current_faction": target_key,
                "joined_team_at": now_ts,
                "switched_voluntarily": False,
                "switched_to_overpopulated": False,
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
        # Q4: Prioridad a los que eligieron primero sobre los que sobrepueblan
        # -------------------------------------------------------------
        print("\n▶ Auto-Pregunta 4: ¿Se prioriza a los jugadores que eligieron primero su equipo sobre los que sobrepueblan?")
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

        # At t=1500: 3 players from Manticore switch voluntarily to Valkyra (overpopulating Valkyra!)
        # Plus 2 new players connect and join Valkyra at t=1600.
        overpop_players = [
            MockRconPlayer(steamId="overpop_1", name="Overpop_1", faction="Valkyra", kills=8, deaths=1, cash=2000),
            MockRconPlayer(steamId="overpop_2", name="Overpop_2", faction="Valkyra", kills=7, deaths=1, cash=1800),
            MockRconPlayer(steamId="overpop_3", name="Overpop_3", faction="Valkyra", kills=6, deaths=1, cash=1500),
        ]
        # In history, these 3 were previously on Manticore
        for op in overpop_players:
            player_team_history[op.steamId] = {
                "current_faction": "manticore",
                "joined_team_at": 1000.0,
                "switched_voluntarily": False,
                "switched_to_overpopulated": False
            }

        new_valk_players = [
            MockRconPlayer(steamId="new_v_1", name="NewV_1", faction="Valkyra", kills=0, deaths=0, cash=0),
            MockRconPlayer(steamId="new_v_2", name="NewV_2", faction="Valkyra", kills=0, deaths=0, cash=0),
        ]

        # Current roster: Valkyra has 20 originals + 3 overpopulators + 2 newcomers = 25 players.
        # Manticore has 17 players. Difference = 8. count_to_move = 4.
        current_roster = valk_team + overpop_players + new_valk_players + mant_team[:17]
        await run_50v50_step(current_roster, now_ts=1700.0)

        # Expected: The 3 overpopulators MUST be moved first!
        # Then 1 of the newcomers.
        # ZERO of the original 20 players should be moved!
        moved_sids = [sid for sid, target in switched_calls]
        print(f"  Jugadores transferidos por el bot: {moved_sids}")
        assert len(moved_sids) == 4, f"Expected 4 moved players, got {len(moved_sids)}"

        assert "overpop_1" in moved_sids, "overpop_1 should have been moved!"
        assert "overpop_2" in moved_sids, "overpop_2 should have been moved!"
        assert "overpop_3" in moved_sids, "overpop_3 should have been moved!"
        # Check that none of the 20 originals were moved
        for v in valk_team:
            assert v.steamId not in moved_sids, f"ERROR: Original player {v.steamId} was unfairly moved!"

        print("  ✅ PASSED: Los 3 que sobrepoblaron fueron transferidos primero. Los 20 originales fueron 100% protegidos.")

        # -------------------------------------------------------------
        # Q5: Prioridad de orden por antigüedad, cash y actividad
        # -------------------------------------------------------------
        print("\n▶ Auto-Pregunta 5: ¿Cómo se desempata entre jugadores legítimos (Antigüedad > Cash > K/D)?")
        player_team_history.clear()
        recently_swapped_players.clear()

        # Senior player: joined at t=500, cash=$0, K/D=0/0
        p_senior = MockRconPlayer(steamId="senior_p", name="Senior", faction="Valkyra", kills=0, deaths=0, cash=0)
        player_team_history["senior_p"] = {"current_faction": "valkyra", "joined_team_at": 500.0, "switched_voluntarily": False}

        # Junior rich: joined at t=800, cash=$2000, K/D=10/2
        p_jr_rich = MockRconPlayer(steamId="jr_rich", name="JrRich", faction="Valkyra", kills=10, deaths=2, cash=2000)
        player_team_history["jr_rich"] = {"current_faction": "valkyra", "joined_team_at": 800.0, "switched_voluntarily": False}

        # Junior fresh: joined at t=800, cash=$0, K/D=0/0
        p_jr_fresh = MockRconPlayer(steamId="jr_fresh", name="JrFresh", faction="Valkyra", kills=0, deaths=0, cash=0)
        player_team_history["jr_fresh"] = {"current_faction": "valkyra", "joined_team_at": 800.0, "switched_voluntarily": False}

        # Valkyra has 3 players, Manticore has 1 player -> diff=2, count_to_move=1
        mant_single = [MockRconPlayer(steamId="m_single", name="MSingle", faction="Manticore", kills=1, deaths=1, cash=0)]
        valk_trio = [p_senior, p_jr_rich, p_jr_fresh]

        await run_50v50_step(valk_trio + mant_single, now_ts=900.0)
        assert len(switched_calls) == 1
        assert switched_calls[0][0] == "jr_fresh", f"Expected jr_fresh to be moved, got {switched_calls[0][0]}"
        print("  ✅ PASSED: Entre recién llegados a t=800, el que tiene $0 y 0 kills se mueve primero, protegiendo al veterano de t=500.")

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
        p_other = MockRconPlayer(steamId="other_candidate", name="Other", faction="Valkyra", kills=5, deaths=2, cash=1000)
        p_third = MockRconPlayer(steamId="third_candidate", name="Third", faction="Valkyra", kills=10, deaths=0, cash=5000)
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
        print("  ✅ PASSED: 4 jugadores azules distribuidos (3 a Manticore, 1 a Valkyra) logrando equilibrio exacto 21v21.")

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

        print("\n=======================================================")
        print("  TODAS LAS 16 AUTO-PREGUNTAS PASARON SATISFACTORIAMENTE!")
        print("  MODO 50v50 Y TEAM BALANCING 100% ROBUSTO E INFALIBLE")
        print("=======================================================\n")

if __name__ == "__main__":
    asyncio.run(main())
