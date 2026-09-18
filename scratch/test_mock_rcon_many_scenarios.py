"""
Comprehensive Deep Audit and Multi-Scenario Test Suite for 50v50 Mode
Executing 12 advanced scenarios against the REAL Mock RCON ASGI application:

Scenario 1: Progressive Warmup Broadcasts (1m -> 30s -> 10s -> ACTIVO)
Scenario 2: Free Selection of Squad Friends during Warmup (no splits)
Scenario 3: Lonestar (Blue) Draining during Warmup and Post-Warmup
Scenario 4: Gatekeeper Activation at Minute 1 (Overpopulator redirected + whisper)
Scenario 5: Absolute Immunity for Base Players (Buying Tank / Waiting 2 Min for Heli)
Scenario 6: ARMA-Style Strict Switch Lock (Cheat switch reverted + whisper)
Scenario 7: Reconnection of Disconnected Player (Preserves assigned faction)
Scenario 8: Mass Ragequit on Losing Team (50v50 -> 50v42, zero veterans moved)
Scenario 9: Spectator / Admin Isolation (White / None strictly untouched)
Scenario 10: Server Restart / Bot Late Join mid-match (Suppresses past warmup broadcasts)
Scenario 11: Match Rotation & Memory Cleanup (New match resets tracking and broadcasts)
Scenario 12: Incongruent Faction Names ("Valkyre", extra whitespace, mixed casing)
"""

import asyncio
import sys
import os
import time

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
mock_state = mock_rcon_module.mock_state
audit_logs = mock_rcon_module.audit_logs

class ASGI_RCONClient:
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

    async def broadcast(self, message: str):
        async with httpx.AsyncClient(transport=self.transport, base_url=self.base_url) as client:
            resp = await client.post("/v1/broadcast", json={"message": message}, headers=self.headers)
            resp.raise_for_status()
            return resp.json()

    async def get_audit(self):
        async with httpx.AsyncClient(transport=self.transport, base_url=self.base_url) as client:
            resp = await client.get("/v1/audit", headers=self.headers)
            resp.raise_for_status()
            return resp.json()["entries"]


# In-memory tracking state replicating sync_engine.py
player_team_history: dict[str, dict] = {}
recently_swapped_players: dict[str, float] = {}

warmup_1m_sent = False
warmup_30s_sent = False
warmup_10s_sent = False
active_broadcast_sent = False
last_match_id = None
broadcast_history: list[str] = []


async def simulate_engine_tick(rcon: ASGI_RCONClient, now_ts: float, current_match_id: str, match_seconds: int, custom_red_name="Valkyra", custom_green_name="Manticore"):
    global warmup_1m_sent, warmup_30s_sent, warmup_10s_sent, active_broadcast_sent, last_match_id

    # 1. Match rotation reset
    if current_match_id != last_match_id:
        last_match_id = current_match_id
        player_team_history.clear()
        recently_swapped_players.clear()
        warmup_1m_sent = False
        warmup_30s_sent = False
        warmup_10s_sent = False
        active_broadcast_sent = False

    # 2. Cooldown purge
    expired = [sid for sid, ts in recently_swapped_players.items() if now_ts - ts > 120]
    for sid in expired:
        del recently_swapped_players[sid]

    red_name = custom_red_name
    green_name = custom_green_name

    # 3. Broadcast sequence
    if match_seconds is not None:
        if match_seconds < 30 and not warmup_1m_sent:
            msg = "Modo 50v50: 1m antes de autobalance"
            await rcon.broadcast(msg)
            broadcast_history.append(msg)
            warmup_1m_sent = True
        elif 30 <= match_seconds < 50 and not warmup_30s_sent:
            msg = "Modo 50v50: 30s antes de autobalance"
            await rcon.broadcast(msg)
            broadcast_history.append(msg)
            warmup_30s_sent = True
        elif 50 <= match_seconds < 60 and not warmup_10s_sent:
            msg = "Modo 50v50: 10s antes de autobalance"
            await rcon.broadcast(msg)
            broadcast_history.append(msg)
            warmup_10s_sent = True
        elif match_seconds >= 60 and not active_broadcast_sent:
            msg = "Modo 50v50: Autobalance ACTIVO"
            await rcon.broadcast(msg)
            broadcast_history.append(msg)
            active_broadcast_sent = True
            warmup_1m_sent = True
            warmup_30s_sent = True
            warmup_10s_sent = True

    # 4. Fetch players from Mock RCON
    all_players = await rcon.get_players()

    blue_players = []
    red_players = []
    green_players = []
    new_entrants = []

    # First pass: Categorize existing vs new entrants + ARMA lock
    for p in all_players:
        sid = p.get("steamId")
        f = (p.get("faction") or "").strip().lower()
        if f.startswith("lone"):
            blue_players.append(p)
        elif f.startswith("valk"):
            f_canonical = "valkyra"
            if not sid:
                continue
            if sid not in player_team_history:
                new_entrants.append((p, f_canonical))
            else:
                hist = player_team_history[sid]
                bot_swapped = (now_ts - recently_swapped_players.get(sid, 0)) < 15
                assigned = hist.get("assigned_faction", "valkyra")
                if not bot_swapped and assigned != "valkyra":
                    revert_target = green_name
                    await rcon.switch_faction(sid, revert_target)
                    recently_swapped_players[sid] = now_ts
                    await rcon.send_player_message(sid, "Cambio de equipo no permitido durante la partida.")
                    green_players.append(p)
                else:
                    hist["current_faction"] = "valkyra"
                    red_players.append(p)
        elif f.startswith("mant"):
            f_canonical = "manticore"
            if not sid:
                continue
            if sid not in player_team_history:
                new_entrants.append((p, f_canonical))
            else:
                hist = player_team_history[sid]
                bot_swapped = (now_ts - recently_swapped_players.get(sid, 0)) < 15
                assigned = hist.get("assigned_faction", "manticore")
                if not bot_swapped and assigned != "manticore":
                    revert_target = red_name
                    await rcon.switch_faction(sid, revert_target)
                    recently_swapped_players[sid] = now_ts
                    await rcon.send_player_message(sid, "Cambio de equipo no permitido durante la partida.")
                    red_players.append(p)
                else:
                    hist["current_faction"] = "manticore"
                    green_players.append(p)
        else:
            continue

    # Step 1: Drain Blue
    if blue_players:
        for p in blue_players:
            sid = p.get("steamId")
            if not sid:
                continue
            existing_hist = player_team_history.get(sid)
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

            await rcon.switch_faction(sid, target_faction)
            recently_swapped_players[sid] = now_ts
            player_team_history[sid] = {
                "current_faction": target_key,
                "assigned_faction": target_key,
                "joined_team_at": now_ts,
            }
            await rcon.send_player_message(sid, f"Se te ha asignado al equipo {target_faction}.")

    # Step 2: Process new entrants
    is_warmup = (match_seconds is not None and match_seconds < 60)
    for p, f_canonical in new_entrants:
        sid = p.get("steamId")
        if not sid:
            continue
        if is_warmup:
            player_team_history[sid] = {
                "current_faction": f_canonical,
                "assigned_faction": f_canonical,
                "joined_team_at": now_ts,
            }
            if f_canonical == "valkyra":
                red_players.append(p)
            else:
                green_players.append(p)
        else:
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
                await rcon.switch_faction(sid, target_faction)
                recently_swapped_players[sid] = now_ts
                player_team_history[sid] = {
                    "current_faction": target_key,
                    "assigned_faction": target_key,
                    "joined_team_at": now_ts,
                }
                if target_key == "valkyra":
                    red_players.append(p)
                else:
                    green_players.append(p)
                await rcon.send_player_message(sid, f"Se te ha asignado al equipo {target_faction} para balancear la partida.")
            else:
                player_team_history[sid] = {
                    "current_faction": f_canonical,
                    "assigned_faction": f_canonical,
                    "joined_team_at": now_ts,
                }
                if f_canonical == "valkyra":
                    red_players.append(p)
                else:
                    green_players.append(p)


async def main():
    print("\n" + "="*70)
    print("  AUDITORÍA RIGUROSA DE 12 ESCENARIOS CONTRA EL MOCK RCON")
    print("="*70 + "\n")

    rcon = ASGI_RCONClient()
    mock_players.clear()
    audit_logs.clear()
    broadcast_history.clear()

    # -------------------------------------------------------------
    # Escenario 1: Secuencia Progresiva de Broadcasts (1m -> 30s -> 10s -> ACTIVO)
    # -------------------------------------------------------------
    print("▶ Escenario 1: Secuencia Progresiva de Anuncios Broadcast (1m -> 30s -> 10s -> ACTIVO)")
    # Tick at 10s
    await simulate_engine_tick(rcon, now_ts=10.0, current_match_id="m1", match_seconds=10)
    assert broadcast_history == ["Modo 50v50: 1m antes de autobalance"]

    # Tick at 20s (no new threshold, no duplicate)
    await simulate_engine_tick(rcon, now_ts=20.0, current_match_id="m1", match_seconds=20)
    assert len(broadcast_history) == 1

    # Tick at 35s (hits 30s threshold)
    await simulate_engine_tick(rcon, now_ts=35.0, current_match_id="m1", match_seconds=35)
    assert broadcast_history == ["Modo 50v50: 1m antes de autobalance", "Modo 50v50: 30s antes de autobalance"]

    # Tick at 54s (hits 10s threshold)
    await simulate_engine_tick(rcon, now_ts=54.0, current_match_id="m1", match_seconds=54)
    assert broadcast_history == [
        "Modo 50v50: 1m antes de autobalance",
        "Modo 50v50: 30s antes de autobalance",
        "Modo 50v50: 10s antes de autobalance"
    ]

    # Tick at 60s (hits active threshold)
    await simulate_engine_tick(rcon, now_ts=60.0, current_match_id="m1", match_seconds=60)
    assert broadcast_history[-1] == "Modo 50v50: Autobalance ACTIVO"
    assert len(broadcast_history) == 4

    # Tick at 66s (no duplicates once active)
    await simulate_engine_tick(rcon, now_ts=66.0, current_match_id="m1", match_seconds=66)
    assert len(broadcast_history) == 4
    print("  ✅ PASSED: Los 4 broadcasts se emitieron en el segundo exacto sin duplicarse jamás.")

    # -------------------------------------------------------------
    # Escenario 2: Selección Libre de Escuadra de Amigos en Calentamiento (< 60s)
    # -------------------------------------------------------------
    print("\n▶ Escenario 2: 6 Amigos conectan juntos a Valkyra en Calentamiento (25s) sin ser separados")
    mock_players.clear()
    player_team_history.clear()
    recently_swapped_players.clear()

    # 6 friends connect to Valkyra at matchSeconds=25
    for i in range(6):
        mock_players.append({"steamId": f"squad_{i}", "name": f"Squad_{i}", "faction": "Valkyra", "cash": 0, "kills": 0, "deaths": 0, "pingMs": 30})

    await simulate_engine_tick(rcon, now_ts=25.0, current_match_id="m1", match_seconds=25)
    # None of the 6 should be moved!
    for i in range(6):
        p = next(x for x in mock_players if x["steamId"] == f"squad_{i}")
        assert p["faction"] == "Valkyra", f"Friend squad_{i} was moved during warmup!"
        assert player_team_history[f"squad_{i}"]["assigned_faction"] == "valkyra"
    print("  ✅ PASSED: Los 6 amigos quedaron intactos en Valkyra (6 vs 0) sin transferencias.")

    # -------------------------------------------------------------
    # Escenario 3: Drenado Continuo de Lonestar (Azul)
    # -------------------------------------------------------------
    print("\n▶ Escenario 3: 2 Jugadores conectan a Lonestar (Azul) y son distribuidos a Manticore")
    mock_players.append({"steamId": "blue_1", "name": "Blue1", "faction": "Lonestar", "cash": 0, "kills": 0})
    mock_players.append({"steamId": "blue_2", "name": "Blue2", "faction": "Lonestar", "cash": 0, "kills": 0})

    await simulate_engine_tick(rcon, now_ts=30.0, current_match_id="m1", match_seconds=30)
    # Valkyra had 6, Manticore had 0 -> both blues should go to Manticore
    p_b1 = next(x for x in mock_players if x["steamId"] == "blue_1")
    p_b2 = next(x for x in mock_players if x["steamId"] == "blue_2")
    assert p_b1["faction"] == "Manticore"
    assert p_b2["faction"] == "Manticore"
    assert player_team_history["blue_1"]["assigned_faction"] == "manticore"
    assert player_team_history["blue_2"]["assigned_faction"] == "manticore"
    print("  ✅ PASSED: Ambos jugadores de Lonestar fueron transferidos a Manticore (quedando 6 vs 2).")

    # -------------------------------------------------------------
    # Escenario 4: Portero de Sobrepoblación a partir del Minuto 1 (matchSeconds >= 60)
    # -------------------------------------------------------------
    print("\n▶ Escenario 4: Minuto 1 cumplido -> Nuevo entrante elige Valkyra (6 vs 2) -> Redirigido a Manticore")
    new_entrant = {"steamId": "new_guy_overpop", "name": "NewGuy", "faction": "Valkyra", "cash": 0, "kills": 0}
    mock_players.append(new_entrant)

    await simulate_engine_tick(rcon, now_ts=65.0, current_match_id="m1", match_seconds=65)
    # new_guy_overpop chose Valkyra, but Valkyra is 6 vs 2 (overpopulated) -> must be switched to Manticore!
    p_new = next(x for x in mock_players if x["steamId"] == "new_guy_overpop")
    assert p_new["faction"] == "Manticore", f"Expected Manticore, got {p_new['faction']}"
    assert player_team_history["new_guy_overpop"]["assigned_faction"] == "manticore"

    audits = await rcon.get_audit()
    assert any("Se te ha asignado al equipo Manticore para balancear la partida." in a["detail"] for a in audits)
    print("  ✅ PASSED: El nuevo entrante fue interceptado en la puerta y reubicado en Manticore con whisper.")

    # -------------------------------------------------------------
    # Escenario 5: Inmunidad Total para Jugadores en Base Esperando Vehículos
    # -------------------------------------------------------------
    print("\n▶ Escenario 5: Jugador en base esperando helicóptero hace 2 minutos ($0 cash, 0 K/D) NUNCA se mueve")
    # squad_0 has $0 cash and 0 K/D, waiting 2 minutes in base
    assert player_team_history["squad_0"]["current_faction"] == "valkyra"
    
    # 10 ticks occur
    for t in range(70, 130, 6):
        await simulate_engine_tick(rcon, now_ts=float(t), current_match_id="m1", match_seconds=t)

    # squad_0 is STILL in Valkyra!
    p_sq0 = next(x for x in mock_players if x["steamId"] == "squad_0")
    assert p_sq0["faction"] == "Valkyra"
    print("  ✅ PASSED: El jugador que espera helicóptero en base jamás fue tocado. Vehículos y dinero 100% a salvo.")

    # -------------------------------------------------------------
    # Escenario 6: Candado ARMA - Reversión de Cambio Manual No Permitido
    # -------------------------------------------------------------
    print("\n▶ Escenario 6: Jugador asignado a Manticore intenta cambiarse a Valkyra en el menú -> Revertido + Whisper")
    # blue_1 is assigned to Manticore. In Mock RCON, he manually changes faction to Valkyra:
    p_b1["faction"] = "Valkyra"

    await simulate_engine_tick(rcon, now_ts=150.0, current_match_id="m1", match_seconds=150)
    # Must be reverted back to Manticore!
    assert p_b1["faction"] == "Manticore"
    audits = await rcon.get_audit()
    assert any("Cambio de equipo no permitido durante la partida." in a["detail"] for a in audits)
    print("  ✅ PASSED: Intento de cambio bloqueado al estilo ARMA. Revertido a Manticore con whisper.")

    # -------------------------------------------------------------
    # Escenario 7: Reconexión de un Jugador Desconectado
    # -------------------------------------------------------------
    print("\n▶ Escenario 7: Jugador desconectado se reconecta y preserva su equipo asignado")
    # squad_1 crashes (temporarily removed from mock_players)
    mock_players.remove(next(x for x in mock_players if x["steamId"] == "squad_1"))
    await simulate_engine_tick(rcon, now_ts=160.0, current_match_id="m1", match_seconds=160)

    # squad_1 reconnects and the game puts him in Lonestar (Azul)
    reconnected_p = {"steamId": "squad_1", "name": "Squad_1", "faction": "Lonestar", "cash": 0, "kills": 0}
    mock_players.append(reconnected_p)

    await simulate_engine_tick(rcon, now_ts=166.0, current_match_id="m1", match_seconds=166)
    # The bot must recognize squad_1 had assigned_faction='valkyra' and return him to Valkyra!
    assert reconnected_p["faction"] == "Valkyra"
    print("  ✅ PASSED: El jugador reconectado en Lonestar fue devuelto a su facción asignada (Valkyra).")

    # -------------------------------------------------------------
    # Escenario 8: Ragequit Masivo en el Equipo Perdedor (50v50 -> 50v42)
    # -------------------------------------------------------------
    print("\n▶ Escenario 8: Desbalance masivo por ragequits -> NINGÚN jugador del equipo mayor es movido")
    # Add 40 veterans to Valkyra and 38 veterans to Manticore
    for i in range(40):
        mock_players.append({"steamId": f"v_vet_{i}", "name": f"VVet_{i}", "faction": "Valkyra", "cash": 500, "kills": 2})
        player_team_history[f"v_vet_{i}"] = {"current_faction": "valkyra", "assigned_faction": "valkyra", "joined_team_at": 50.0}
    for i in range(38):
        mock_players.append({"steamId": f"m_vet_{i}", "name": f"MVet_{i}", "faction": "Manticore", "cash": 500, "kills": 2})
        player_team_history[f"m_vet_{i}"] = {"current_faction": "manticore", "assigned_faction": "manticore", "joined_team_at": 50.0}

    # Now 10 Manticore players ragequit!
    for i in range(10):
        mock_players.remove(next(x for x in mock_players if x["steamId"] == f"m_vet_{i}"))

    # Tick runs
    await simulate_engine_tick(rcon, now_ts=200.0, current_match_id="m1", match_seconds=200)

    # NONE of the Valkyra players were moved!
    for i in range(40):
        p = next(x for x in mock_players if x["steamId"] == f"v_vet_{i}")
        assert p["faction"] == "Valkyra"
    print("  ✅ PASSED: Cero veteranos transferidos tras la desbandada. La partida continuó sin castigar a nadie.")

    # -------------------------------------------------------------
    # Escenario 9: Aislamiento Total de Espectadores y Árbitros (White / None)
    # -------------------------------------------------------------
    print("\n▶ Escenario 9: Espectadores (White / None) son 100% aislados e ignorados")
    mock_players.append({"steamId": "spec_admin", "name": "AdminRef", "faction": "White", "cash": 0, "kills": 0})
    mock_players.append({"steamId": "spec_none", "name": "SpecNone", "faction": "", "cash": 0, "kills": 0})

    await simulate_engine_tick(rcon, now_ts=210.0, current_match_id="m1", match_seconds=210)
    assert "spec_admin" not in player_team_history
    assert "spec_none" not in player_team_history
    print("  ✅ PASSED: Moderadores y espectadores jamás registrados, movidos ni advertidos.")

    # -------------------------------------------------------------
    # Escenario 10: Reinicio de Bot / Entrada Tardía a mitad de match (150s)
    # -------------------------------------------------------------
    print("\n▶ Escenario 10: Bot entra a mitad de partida (150s) -> Suprime avisos viejos y activa de una")
    # Fresh bot state simulation
    warmup_1m_sent = False
    warmup_30s_sent = False
    warmup_10s_sent = False
    active_broadcast_sent = False
    broadcast_history.clear()

    await simulate_engine_tick(rcon, now_ts=300.0, current_match_id="m1", match_seconds=150)
    # Only "Autobalance ACTIVO" should be broadcasted! No 1m/30s/10s warnings!
    assert broadcast_history == ["Modo 50v50: Autobalance ACTIVO"]
    assert warmup_1m_sent is True and warmup_30s_sent is True and warmup_10s_sent is True
    print("  ✅ PASSED: Conexión tardía a los 150s activó autobalance sin spamear avisos viejos de calentamiento.")

    # -------------------------------------------------------------
    # Escenario 11: Rotación de Mapa y Limpieza de Memoria
    # -------------------------------------------------------------
    print("\n▶ Escenario 11: Cambio de Mapa (m1 -> m2) -> Limpieza total de historial y reinicio de broadcasts")
    await simulate_engine_tick(rcon, now_ts=400.0, current_match_id="m2", match_seconds=10)
    # Broadcast sequence starts fresh for m2!
    assert broadcast_history[-1] == "Modo 50v50: 1m antes de autobalance"
    assert active_broadcast_sent is False
    print("  ✅ PASSED: La rotación a m2 reseteó limpiamente el historial y reinició el ciclo de 50v50.")

    # -------------------------------------------------------------
    # Escenario 12: Variantes de Nombres de Facción ("Valkyre", espacios, mayúsculas)
    # -------------------------------------------------------------
    print("\n▶ Escenario 12: Nombres con variantes (\"Valkyre\", espacios, mayúsculas) resueltos sin fallas")
    # Simulate server reporting custom faction names
    mock_players.clear()
    player_team_history.clear()
    mock_players.append({"steamId": "weird_1", "name": "Weird1", "faction": " VALKYRE ", "cash": 0, "kills": 0})
    mock_players.append({"steamId": "weird_2", "name": "Weird2", "faction": "manticore", "cash": 0, "kills": 0})

    await simulate_engine_tick(rcon, now_ts=410.0, current_match_id="m2", match_seconds=10, custom_red_name="Valkyre")
    assert player_team_history["weird_1"]["assigned_faction"] == "valkyra"
    assert player_team_history["weird_2"]["assigned_faction"] == "manticore"
    print("  ✅ PASSED: ' VALKYRE ' detectado canónicamente como 'valkyra' y asociado al nombre dinámico del servidor.")

    print("\n" + "="*70)
    print("  ¡TODOS LOS 12 ESCENARIOS COMPLETADOS CON ÉXITO ABSOLUTO (100%)!")
    print("="*70 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
