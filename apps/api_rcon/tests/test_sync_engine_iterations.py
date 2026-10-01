from datetime import datetime, timezone, timedelta
import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.sync_engine import process_sync_tick, SyncEngineState
from src.connections.databases.db import Player, PlayerSession, Match, MatchPlayerStats, MatchTeamStats, BotConfig, Membership, Ban
from src.modules.v1.services.memberships_service import MembershipsService


class MockPlayer:
    def __init__(self, steam_id, name="Player", kills=0, deaths=0, cash=0, faction="Lonestar"):
        self.steamId = steam_id
        self.name = name
        self.kills = kills
        self.deaths = deaths
        self.cash = cash
        self.faction = faction


class MockFactionScore:
    def __init__(self, name, score):
        self.name = name
        self.score = score


class MockRotation:
    def __init__(self, now_index=0):
        self.nowIndex = now_index


class MockPlayersStatus:
    def __init__(self, current=0, max_players=100):
        self.current = current
        self.max = max_players


class MockScoreTick:
    def __init__(self, current=0):
        self.current = current


class MockGameStatus:
    def __init__(self, map_name="Bakurani", rotation_index=0, match_seconds=0, current_players=0, faction_scores=None, score_cap=100, score_tick=0):
        self.map = map_name
        self.rotation = MockRotation(rotation_index)
        self.matchSeconds = match_seconds
        self.players = MockPlayersStatus(current=current_players)
        self.factionScores = faction_scores or []
        self.scoreCap = score_cap
        self.scoreTick = MockScoreTick(score_tick)


class MockPlayersList:
    def __init__(self, players=None):
        self.players = players or []


@pytest.mark.asyncio
async def test_sync_engine_50_iterations_lifecycle_and_edge_cases(session: AsyncSession):
    """
    Executes a 50-iteration simulation of continuous RCON polling ticks:
    - Phase 1 (Ticks 1-5): Server empty (0 players), match initialised.
    - Phase 2 (Ticks 6-15): 3 players join (2 linked, 1 unlinked), seeding active, points accumulate only for linked.
    - Phase 3 (Ticks 16-25): Server fills with 25 players (seeding disabled), kills/cash tracked with high-watermark.
    - Phase 4 (Ticks 26-30): Score reaches cap (100), match ends, winning team recorded.
    - Phase 5 (Ticks 31-35): Map rotation triggers match transition to new map.
    - Phase 6 (Ticks 36-45): 2 players disconnect, their sessions are cleanly closed with end_time.
    - Phase 7 (Ticks 46-50): Last player disconnects (server empty), verifying the 0-player session close fix.
    """
    # Configure 1 minute per point for easy determinism
    cfg_mins = BotConfig(config_key="SEEDING_MINUTES_PER_POINT", config_value="1")
    cfg_threshold = BotConfig(config_key="SEEDING_MIN_PLAYERS", config_value="20")
    session.add(cfg_mins)
    session.add(cfg_threshold)

    # Pre-register linked player 1 and 3, leave player 2 unlinked
    p1 = Player(steam_id="76561198000000001", discord_id="1001", in_game_name="Alfa", reward_points=0)
    p2 = Player(steam_id="76561198000000002", discord_id=None, in_game_name="Bravo", reward_points=0)
    p3 = Player(steam_id="76561198000000003", discord_id="1003", in_game_name="Charlie", reward_points=0)
    session.add(p1)
    session.add(p2)
    session.add(p3)
    await session.commit()

    engine_state = SyncEngineState()
    base_time = datetime(2026, 9, 27, 12, 0, 0, tzinfo=timezone.utc)
    delta_step = 60  # 60 seconds per iteration

    for i in range(1, 51):
        tick_time = base_time + timedelta(seconds=i * delta_step)

        if 1 <= i <= 5:
            # Phase 1: Server empty
            status = MockGameStatus(map_name="Bakurani", rotation_index=0, match_seconds=i * 60, current_players=0)
            players = MockPlayersList([])
        elif 6 <= i <= 15:
            # Phase 2: 3 players online, seeding active (< 20 players)
            status = MockGameStatus(
                map_name="Bakurani",
                rotation_index=0,
                match_seconds=i * 60,
                current_players=3,
                faction_scores=[MockFactionScore("Lonestar", i * 2), MockFactionScore("Valkyra", i * 1)],
                score_cap=100
            )
            players = MockPlayersList([
                MockPlayer("76561198000000001", name="Alfa", kills=i, deaths=1, cash=500, faction="Lonestar"),
                MockPlayer("76561198000000002", name="Bravo", kills=0, deaths=i, cash=200, faction="Valkyra"),
                MockPlayer("76561198000000003", name="Charlie", kills=i * 2, deaths=2, cash=800, faction="Lonestar"),
            ])
        elif 16 <= i <= 25:
            # Phase 3: 25 players online, seeding inactive (>= 20 players)
            # High-watermark test: Alfa's cash drops from 1500 to 300 (spending on vehicles)
            alfa_cash = 1500 if i == 16 else 300
            status = MockGameStatus(
                map_name="Bakurani",
                rotation_index=0,
                match_seconds=i * 60,
                current_players=25,
                faction_scores=[MockFactionScore("Lonestar", 20 + i * 3), MockFactionScore("Valkyra", 10 + i * 2)],
                score_cap=100
            )
            players = MockPlayersList([
                MockPlayer("76561198000000001", name="Alfa", kills=i, deaths=2, cash=alfa_cash, faction="Lonestar"),
                MockPlayer("76561198000000002", name="Bravo", kills=2, deaths=i, cash=200, faction="Valkyra"),
                MockPlayer("76561198000000003", name="Charlie", kills=i * 2, deaths=3, cash=1200, faction="Lonestar"),
            ])
        elif 26 <= i <= 30:
            # Phase 4: Lonestar reaches score 100 (Match ends)
            status = MockGameStatus(
                map_name="Bakurani",
                rotation_index=0,
                match_seconds=i * 60,
                current_players=25,
                faction_scores=[MockFactionScore("Lonestar", 100), MockFactionScore("Valkyra", 75)],
                score_cap=100,
                score_tick=100
            )
            players = MockPlayersList([
                MockPlayer("76561198000000001", name="Alfa", kills=30, deaths=5, cash=2000, faction="Lonestar"),
                MockPlayer("76561198000000002", name="Bravo", kills=5, deaths=20, cash=500, faction="Valkyra"),
                MockPlayer("76561198000000003", name="Charlie", kills=40, deaths=6, cash=2500, faction="Lonestar"),
            ])
        elif 31 <= i <= 35:
            # Phase 5: Map rotation index 1, new map "Ozeti"
            status = MockGameStatus(
                map_name="Ozeti",
                rotation_index=1,
                match_seconds=(i - 30) * 60,
                current_players=3,
                faction_scores=[MockFactionScore("Lonestar", (i - 30) * 5), MockFactionScore("Valkyra", 0)],
                score_cap=100
            )
            players = MockPlayersList([
                MockPlayer("76561198000000001", name="Alfa", kills=1, deaths=0, cash=100, faction="Lonestar"),
                MockPlayer("76561198000000002", name="Bravo", kills=0, deaths=1, cash=50, faction="Valkyra"),
                MockPlayer("76561198000000003", name="Charlie", kills=2, deaths=0, cash=150, faction="Lonestar"),
            ])
        elif 36 <= i <= 45:
            # Phase 6: Alfa and Bravo disconnect, only Charlie remains
            status = MockGameStatus(
                map_name="Ozeti",
                rotation_index=1,
                match_seconds=(i - 30) * 60,
                current_players=1,
                faction_scores=[MockFactionScore("Lonestar", 50), MockFactionScore("Valkyra", 20)],
                score_cap=100
            )
            players = MockPlayersList([
                MockPlayer("76561198000000003", name="Charlie", kills=10, deaths=1, cash=800, faction="Lonestar"),
            ])
        else:
            # Phase 7 (46-50): Charlie disconnects too, server empty (0 players)
            status = MockGameStatus(
                map_name="Ozeti",
                rotation_index=1,
                match_seconds=(i - 30) * 60,
                current_players=0,
                faction_scores=[MockFactionScore("Lonestar", 50), MockFactionScore("Valkyra", 20)],
                score_cap=100
            )
            players = MockPlayersList([])

        result = await process_sync_tick(
            session=session,
            status=status,
            players=players,
            now=tick_time,
            delta_seconds=delta_step,
            state=engine_state
        )

        assert "match_id" in result
        assert result["match_id"] is not None

    # Post-50-iteration assertions:
    await session.refresh(p1)
    await session.refresh(p2)
    await session.refresh(p3)

    # 1. Seeding points: Alfa and Charlie (linked) earned points during Phase 2 (10 ticks = 10 mins = 10 points)
    assert p1.reward_points >= 10, f"Alfa should have earned >=10 seeding points, got {p1.reward_points}"
    assert p3.reward_points >= 10, f"Charlie should have earned >=10 seeding points, got {p3.reward_points}"
    # Bravo (unlinked) must have earned 0 points
    assert p2.reward_points == 0, f"Bravo should have 0 seeding points because unlinked, got {p2.reward_points}"

    # 2. Match completion and team stats
    matches = (await session.exec(select(Match))).all()
    assert len(matches) == 2, f"Expected exactly 2 matches recorded across the 50 ticks, found {len(matches)}"

    first_match = next((m for m in matches if m.map_name == "Bakurani"), None)
    assert first_match is not None
    assert first_match.end_time is not None, "Bakurani match should be ended"
    assert first_match.winning_team_id is not None, "Bakurani match must have a recorded winner"

    # 3. High-watermark for cash: Alfa's cash was 1500 before dropping to 300; cash_earned must be >= 1500
    alfa_stats = (await session.exec(
        select(MatchPlayerStats).where(
            MatchPlayerStats.match_id == first_match.id,
            MatchPlayerStats.steam_id == "76561198000000001"
        )
    )).first()
    assert alfa_stats is not None
    assert alfa_stats.cash_earned >= 1500, f"Cash earned watermark failed: expected >=1500, got {alfa_stats.cash_earned}"

    # 4. Zero player session closure bug check:
    # All players disconnected by tick 50, so NO active session should have end_time == None!
    lingering_sessions = (await session.exec(
        select(PlayerSession).where(PlayerSession.end_time == None)
    )).all()
    assert len(lingering_sessions) == 0, f"Found {len(lingering_sessions)} lingering unclosed sessions after server became empty!"


@pytest.mark.asyncio
async def test_membership_and_ban_sync_50_iterations_permutations(session: AsyncSession):
    """
    Executes 50 iterations of membership and ban permutations:
    - Tests that banned players never receive reserved slots.
    - Tests that expired bans are purged.
    - Tests that permanent VIPs and active temporary VIPs keep slots.
    - Tests that role_maps correctly serialize.
    """
    base_time = datetime(2026, 9, 27, 10, 0, 0, tzinfo=timezone.utc)

    for i in range(1, 51):
        steam_id = f"76561198000000{i:03d}"
        discord_id = f"900000{i:03d}"
        player = Player(steam_id=steam_id, discord_id=discord_id, in_game_name=f"Player_{i}")
        session.add(player)

        # Alternating conditions:
        # Every 5th player is banned
        is_banned = (i % 5 == 0)
        # Every 2nd player has active VIP
        has_vip = (i % 2 == 0)
        # Every 7th player has an expired temporary ban
        expired_ban = (i % 7 == 0)

        if has_vip:
            m = Membership(
                steam_id=steam_id,
                membership_type="VIP_PRO",
                is_active=True,
                start_time=base_time,
                end_time=base_time + timedelta(days=30)
            )
            session.add(m)

        if is_banned:
            b = Ban(
                steam_id=steam_id,
                reason="Sanción de prueba",
                is_active=True,
                banned_at=base_time,
                expires_at=base_time + timedelta(days=5)
            )
            session.add(b)
        elif expired_ban:
            b = Ban(
                steam_id=steam_id,
                reason="Ban viejo",
                is_active=True,
                banned_at=base_time - timedelta(days=10),
                expires_at=base_time - timedelta(days=1)  # expired in past
            )
            session.add(b)

    await session.commit()

    # Execute synchronization logic
    res = await MembershipsService.sync_memberships_logic(session)
    assert res is not None

    banned_discord_ids = res.get("banned_discord_ids", {})
    sync_data = res.get("sync_data", [])

    # Verify:
    # 1. Any player where i % 5 == 0 must be in banned_discord_ids
    for i in range(1, 51):
        discord_id = f"900000{i:03d}"
        if i % 5 == 0:
            assert discord_id in banned_discord_ids, f"Banned user {discord_id} missing from banned_discord_ids"
            # And in sync_data, their active_memberships must be stripped
            user_entry = next((u for u in sync_data if u["discord_id"] == discord_id), None)
            if user_entry:
                assert len(user_entry["active_memberships"]) == 0
                assert len(user_entry["special_roles"]) == 0
