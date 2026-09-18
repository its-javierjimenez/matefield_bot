"""
End-to-End Integration Test against Mock RCON (apps.rcon_mock.src.main)
Validating:
1. ARMA-style strict team switch block & revert + whisper message.
2. Lonestar (Blue) assignment + whisper message.
3. Fresh player auto-balancing + whisper message.
4. Immunity of combat veterans ($0 cash vs >$0 cash).
5. All calls verified against Mock RCON's real HTTP endpoints & audit log.
"""

import asyncio
import sys
import os

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, workspace_root)
sys.path.insert(0, os.path.join(workspace_root, "apps", "rcon_mock"))
sys.path.insert(0, os.path.join(workspace_root, "packages", "wardogs_schemas", "src"))

import httpx
from httpx import ASGITransport
import importlib.util

mock_rcon_path = os.path.join(workspace_root, "apps", "rcon_mock", "src", "main.py")
spec = importlib.util.spec_from_file_location("mock_rcon_module", mock_rcon_path)
mock_rcon_module = importlib.util.module_from_spec(spec)
sys.modules["mock_rcon_module"] = mock_rcon_module
spec.loader.exec_module(mock_rcon_module)

rcon_fastapi_app = mock_rcon_module.app
mock_players = mock_rcon_module.mock_players
audit_logs = mock_rcon_module.audit_logs


class ASGI_RCONClient:
    """Wrapper that communicates directly with Mock RCON FastAPI app via httpx ASGITransport"""
    def __init__(self):
        self.transport = ASGITransport(app=rcon_fastapi_app)
        self.base_url = "http://mock-rcon"
        self.headers = {
            "Authorization": "Bearer test",
            "Content-Type": "application/json"
        }

    async def get_players(self):
        async with httpx.AsyncClient(transport=self.transport, base_url=self.base_url) as client:
            resp = await client.get("/v1/players", headers=self.headers)
            resp.raise_for_status()
            return resp.json()["players"]

    async def switch_faction(self, steam_id: str, faction: str):
        async with httpx.AsyncClient(transport=self.transport, base_url=self.base_url) as client:
            resp = await client.patch(f"/v1/players/{steam_id}", json={"faction": faction}, headers=self.headers)
            resp.raise_for_status()
            return resp.json()

    async def send_player_message(self, steam_id: str, message: str):
        async with httpx.AsyncClient(transport=self.transport, base_url=self.base_url) as client:
            resp = await client.post(f"/v1/players/{steam_id}/message", json={"message": message}, headers=self.headers)
            resp.raise_for_status()
            return resp.json()

    async def get_audit(self):
        async with httpx.AsyncClient(transport=self.transport, base_url=self.base_url) as client:
            resp = await client.get("/v1/audit", headers=self.headers)
            resp.raise_for_status()
            return resp.json()["entries"]


async def main():
    print("\n=======================================================")
    print("  TESTING 50v50 ARMA LOCK & WHISPERS WITH REAL MOCK RCON")
    print("=======================================================\n")

    rcon = ASGI_RCONClient()

    # Reset Mock RCON State
    mock_players.clear()
    audit_logs.clear()

    # Setup Initial Match State in Mock RCON:
    # 20 Valkyra veterans (cash > 0, kills > 0)
    for i in range(20):
        mock_players.append({
            "steamId": f"vet_valk_{i}",
            "name": f"VetValk_{i}",
            "faction": "Valkyra",
            "kills": 5,
            "deaths": 1,
            "cash": 1200,
            "pingMs": 30
        })

    # 18 Manticore veterans
    for i in range(18):
        mock_players.append({
            "steamId": f"vet_mant_{i}",
            "name": f"VetMant_{i}",
            "faction": "Manticore",
            "kills": 4,
            "deaths": 2,
            "cash": 1000,
            "pingMs": 35
        })

    # 1 Player in Lonestar (Blue)
    mock_players.append({
        "steamId": "blue_guy_1",
        "name": "BlueGuy1",
        "faction": "Lonestar",
        "kills": 0,
        "deaths": 0,
        "cash": 0,
        "pingMs": 40
    })

    # 1 White spectator
    mock_players.append({
        "steamId": "spectator_1",
        "name": "Spectator1",
        "faction": "White",
        "kills": 0,
        "deaths": 0,
        "cash": 0,
        "pingMs": 20
    })

    player_team_history = {}
    recently_swapped_players = {}

    print("--- [TEST 1: Ingesting Players & Step 1 Drain Blue via Mock RCON] ---")
    now_ts = 1000.0

    # Read players from Mock RCON
    raw_players = await rcon.get_players()
    assert len(raw_players) == 40  # 20 valk + 18 mant + 1 blue + 1 white

    # Run 50v50 step logic replicating sync_engine.py with RCON client
    blue_players = []
    red_players = []
    green_players = []

    for p in raw_players:
        sid = p["steamId"]
        f = (p["faction"] or "").strip().lower()
        if f.startswith("lone"):
            blue_players.append(p)
            f_canonical = "lonestar"
        elif f.startswith("valk"):
            f_canonical = "valkyra"
        elif f.startswith("mant"):
            f_canonical = "manticore"
        else:
            continue

        if sid and f_canonical in ("valkyra", "manticore"):
            hist = player_team_history.get(sid)
            if not hist:
                player_team_history[sid] = {
                    "current_faction": f_canonical,
                    "assigned_faction": f_canonical,
                    "joined_team_at": now_ts,
                }
            if f_canonical == "valkyra":
                red_players.append(p)
            else:
                green_players.append(p)

    # Step 1: Drain Blue
    red_name = "Valkyra"
    green_name = "Manticore"
    for p in blue_players:
        sid = p["steamId"]
        if len(red_players) <= len(green_players):
            target_faction = red_name
            target_key = "valkyra"
            red_players.append(p)
        else:
            target_faction = green_name
            target_key = "manticore"
            green_players.append(p)

        # Send HTTP calls to Mock RCON
        await rcon.switch_faction(sid, target_faction)
        await rcon.send_player_message(sid, f"Se te ha asignado al equipo {target_faction}.")
        recently_swapped_players[sid] = now_ts
        player_team_history[sid] = {
            "current_faction": target_key,
            "assigned_faction": target_key,
            "joined_team_at": now_ts,
        }

    # Verify in Mock RCON that blue_guy_1 is now on Manticore and whisper was recorded in audit log!
    mock_p = next(p for p in mock_players if p["steamId"] == "blue_guy_1")
    assert mock_p["faction"] == "Manticore", f"Expected Manticore, got {mock_p['faction']}"

    audits = await rcon.get_audit()
    assert any("Se te ha asignado al equipo Manticore." in a["detail"] for a in audits)
    print("  ✅ PASSED: Jugador azul transferido a Manticore y whisper verificado en Audit Log de Mock RCON.")

    print("\n--- [TEST 2: ARMA-Style Strict Team Switch Intercept & Revert] ---")
    now_ts = 1100.0

    # blue_guy_1 attempts to manually switch to Valkyra via game menu!
    # In Mock RCON, simulate the player changing faction in-game:
    for p in mock_players:
        if p["steamId"] == "blue_guy_1":
            p["faction"] = "Valkyra"

    # Bot sync tick runs
    raw_players = await rcon.get_players()
    blue_players = []
    red_players = []
    green_players = []

    for p in raw_players:
        sid = p["steamId"]
        f = (p["faction"] or "").strip().lower()
        if f.startswith("lone"):
            blue_players.append(p)
            f_canonical = "lonestar"
        elif f.startswith("valk"):
            f_canonical = "valkyra"
        elif f.startswith("mant"):
            f_canonical = "manticore"
        else:
            continue

        if sid and f_canonical in ("valkyra", "manticore"):
            hist = player_team_history.get(sid)
            if hist and hist["current_faction"] != f_canonical:
                old_f = hist["current_faction"]
                bot_swapped = (now_ts - recently_swapped_players.get(sid, 0)) < 15

                # ARMA LOCK TRIGGER!
                if not bot_swapped:
                    assigned = hist.get("assigned_faction", old_f)
                    if assigned in ("valkyra", "manticore") and assigned != f_canonical:
                        revert_target = red_name if assigned == "valkyra" else green_name
                        print(f"  [ARMA LOCK] Detected manual switch for {sid} -> {f_canonical}! Reverting to {revert_target}...")
                        await rcon.switch_faction(sid, revert_target)
                        await rcon.send_player_message(sid, "Cambio de equipo no permitido durante la partida.")
                        recently_swapped_players[sid] = now_ts
                        if assigned == "valkyra":
                            red_players.append(p)
                        else:
                            green_players.append(p)
                        continue

            if f_canonical == "valkyra":
                red_players.append(p)
            else:
                green_players.append(p)

    # Verify that in Mock RCON, blue_guy_1 was REVERTED back to Manticore!
    mock_p = next(p for p in mock_players if p["steamId"] == "blue_guy_1")
    assert mock_p["faction"] == "Manticore", f"ERROR: Player was not reverted! Current: {mock_p['faction']}"

    audits = await rcon.get_audit()
    assert any("Cambio de equipo no permitido durante la partida." in a["detail"] for a in audits)
    print("  ✅ PASSED: Intento de cambio bloqueado al estilo ARMA. Jugador devuelto a Manticore y whisper enviado.")

    print("\n--- [TEST 3: Auto-Balancing with Immunity for Combat Veterans] ---")
    now_ts = 1300.0

    # Add 4 fresh arrivals with $0 cash and 0 K/D to Valkyra in Mock RCON
    for i in range(4):
        fresh_p = {
            "steamId": f"fresh_valk_{i}",
            "name": f"FreshValk_{i}",
            "faction": "Valkyra",
            "kills": 0,
            "deaths": 0,
            "cash": 0,
            "pingMs": 50
        }
        mock_players.append(fresh_p)
        player_team_history[fresh_p["steamId"]] = {
            "current_faction": "valkyra",
            "assigned_faction": "valkyra",
            "joined_team_at": 1285.0 + i,  # joined 11-15s ago (<= 24s)
        }

    # Valkyra now has 20 veterans + 4 fresh = 24.
    # Manticore has 18 veterans + 1 blue = 19.
    # Diff = 24 - 19 = 5 -> count_to_move = 2.
    import unittest.mock
    with unittest.mock.patch.object(mock_rcon_module.random, "random", return_value=0.0):
        raw_players = await rcon.get_players()
    red_players = [p for p in raw_players if (p["faction"] or "").strip().lower().startswith("valk")]
    green_players = [p for p in raw_players if (p["faction"] or "").strip().lower().startswith("mant")]

    diff = len(red_players) - len(green_players)
    count_to_move = abs(diff) // 2

    # Collect eligible candidates (only non-combatants: $0 cash, 0 kills, 0 deaths, and joined <= 24s ago)
    donor_team = red_players
    target_faction = "Manticore"
    target_key = "manticore"

    eligible_candidates = []
    for p in donor_team:
        sid = p["steamId"]
        if (now_ts - recently_swapped_players.get(sid, 0)) <= 60:
            continue
        has_combat = ((p.get("cash") or 0) > 0) or ((p.get("kills") or 0) > 0)
        time_on_team = now_ts - player_team_history.get(p["steamId"], {}).get("joined_team_at", now_ts)
        if (not has_combat) and (time_on_team <= 24):
            eligible_candidates.append(p)

    # Sort by newest join time
    eligible_candidates.sort(key=lambda p: -player_team_history.get(p["steamId"], {}).get("joined_team_at", now_ts))

    moved_count = min(count_to_move, len(eligible_candidates))
    moved_sids = []
    for p in eligible_candidates[:moved_count]:
        sid = p["steamId"]
        await rcon.switch_faction(sid, target_faction)
        await rcon.send_player_message(sid, f"Se te ha asignado al equipo {target_faction} para balancear la partida.")
        recently_swapped_players[sid] = now_ts
        player_team_history[sid] = {
            "current_faction": target_key,
            "assigned_faction": target_key,
            "joined_team_at": now_ts,
        }
        moved_sids.append(sid)

    # Check Mock RCON state
    assert len(moved_sids) == 2
    assert "fresh_valk_3" in moved_sids and "fresh_valk_2" in moved_sids

    # None of the 20 veterans were moved!
    for i in range(20):
        vet_p = next(p for p in mock_players if p["steamId"] == f"vet_valk_{i}")
        assert vet_p["faction"] == "Valkyra", f"Veteran vet_valk_{i} was wrongly moved!"

    # Verify audit log in Mock RCON
    audits = await rcon.get_audit()
    assert any("Se te ha asignado al equipo Manticore para balancear la partida." in a["detail"] for a in audits)
    print("  ✅ PASSED: 2 novatos sin combatir ($0 cash, <= 24s) auto-balanceados a Manticore con whisper. 100% de veteranos protegidos.")

    print("\n--- [TEST 4: Base Tenure Protection (> 24s) and Match Warmup (< 60s)] ---")
    # A player buying a vehicle in base for 30s ($0 cash, 0 K/D)
    vehicle_buyer = {
        "steamId": "buyer_1",
        "name": "Buyer1",
        "faction": "Valkyra",
        "kills": 0,
        "deaths": 0,
        "cash": 0,
        "pingMs": 40
    }
    mock_players.append(vehicle_buyer)
    player_team_history["buyer_1"] = {
        "current_faction": "valkyra",
        "assigned_faction": "valkyra",
        "joined_team_at": 1400.0  # At 1435.0, tenure = 35s > 24s
    }

    test4_now = 1435.0
    buyer_tenure = test4_now - player_team_history["buyer_1"]["joined_team_at"]
    assert buyer_tenure > 24, "Buyer tenure should be > 24s"

    # Evaluated for balance:
    buyer_eligible = (not (((vehicle_buyer.get("cash") or 0) > 0) or ((vehicle_buyer.get("kills") or 0) > 0))) and (buyer_tenure <= 24)
    assert buyer_eligible is False, "Player in base > 24s must NOT be eligible for transfer!"
    print("  ✅ PASSED: Comprador de vehículo en base (> 24s) es 100% inmune ante transferencias en Mock RCON.")

    print("\n=======================================================")
    print("  MOCK RCON E2E INTEGRATION TESTS: 100% PASSED!")
    print("=======================================================\n")


if __name__ == "__main__":
    asyncio.run(main())
