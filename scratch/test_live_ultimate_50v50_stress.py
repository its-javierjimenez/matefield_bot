import asyncio
import httpx
import json
import subprocess
import time

MOCK_URL = "http://localhost:9001"
API_URL = "http://localhost:8000/api"
API_KEY = "local-api-key"
RCON_AUTH = {"Authorization": "Bearer test"}
API_HEADERS = {"X-API-Key": API_KEY}

def check_db():
    cmd = ["docker", "exec", "matefield_db_local", "psql", "-U", "matefield_user", "-d", "matefield_db", "-t", "-c", "SELECT config_key, config_value FROM bot_config WHERE config_key LIKE 'MODE_50V50%';"]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    lines = [l.strip() for l in res.stdout.strip().split("\n") if l.strip()]
    data = {}
    for line in lines:
        parts = [p.strip() for p in line.split("|")]
        if len(parts) == 2:
            data[parts[0]] = parts[1]
    return data

import sys
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

async def run_stress_suite():
    print("=" * 80)
    print(">>> INICIANDO TEST DE ESTRES EXHAUSTIVO 50v50 CONTRA CONTENEDORES EN VIVO")

    print("   Contenedores: api_rcon_local, matefield_db_local, mock_rcon, discord_bot_local")
    print("=" * 80)

    async with httpx.AsyncClient(timeout=30.0) as client:
        # -------------------------------------------------------------
        # 0. SETUP: Limpieza y Activación del Modo 50v50
        # -------------------------------------------------------------
        print("\n[PASO 0] Activando Modo 50v50 vía API...")
        r = await client.post(f"{API_URL}/v1/mode50v50/enable", headers=API_HEADERS)
        print(f"  * API /v1/mode50v50/enable: {r.status_code} -> {r.json()}")
        assert r.status_code == 200, "Error activando 50v50 vía API"

        # Verificar BD del contenedor
        db_state = check_db()
        print(f"  * Estado en DB (Postgres contenedor): {db_state}")
        assert db_state.get("MODE_50V50_STATE") == "active", f"DB state no es active: {db_state}"
        assert db_state.get("MODE_50V50_ENABLED") == "true", f"DB enabled no es true: {db_state}"

        # Verificar Mock RCON config
        cfg = (await client.get(f"{MOCK_URL}/v1/config", headers=RCON_AUTH)).json()
        assert "bLockOverpopulatedTeamsConfig=false" in cfg["text"], "Team balancing nativo no fue desactivado en RCON!"
        print("  * RCON Config: bLockOverpopulatedTeamsConfig=false CONFIRMADO.")

        # -------------------------------------------------------------
        # 1. ESCENARIO: FLUJO GRANDE ANTES DE LOS 10s (WARMUP)
        #    35 Manticore vs 5 Valkyra (Total 40 jugadores entran en <10s)
        # -------------------------------------------------------------
        print("\n[PASO 1] Simulación: Influx masivo antes de los 10s (match_seconds=2)")
        await client.post(f"{MOCK_URL}/mock/set_match_seconds?seconds=2")

        players_p1 = []
        # 35 entran a Manticore
        for i in range(1, 36):
            players_p1.append({
                "name": f"Mant_{i}",
                "steamId": f"7656119810000{i:04d}",
                "faction": "Manticore",
                "kills": 0,
                "deaths": 0,
                "cash": 0,
                "pingMs": 30
            })
        # 5 entran a Valkyra
        for i in range(1, 6):
            players_p1.append({
                "name": f"Valk_{i}",
                "steamId": f"7656119820000{i:04d}",
                "faction": "Valkyre",
                "kills": 0,
                "deaths": 0,
                "cash": 0,
                "pingMs": 30
            })
        
        await client.post(f"{MOCK_URL}/mock/set_players", json=players_p1)
        print(f"  * Jugadores inyectados: 35 Manticore, 5 Valkyra (Diferencia = 30)")
        print("  * Esperando 7 segundos para que el ciclo de 6s del bot evalúe...")
        await asyncio.sleep(7.5)

        # Evaluar resultado en Mock RCON
        pl_resp = (await client.get(f"{MOCK_URL}/v1/players", headers=RCON_AUTH)).json()["players"]
        c_mant = sum(1 for p in pl_resp if p["faction"].lower().startswith("mant"))
        c_valk = sum(1 for p in pl_resp if p["faction"].lower().startswith("valk"))
        c_lone = sum(1 for p in pl_resp if p["faction"].lower().startswith("lone"))
        diff = abs(c_mant - c_valk)

        print(f"  * Resultado tras evaluación del bot: Manticore={c_mant}, Valkyra={c_valk}, Lonestar={c_lone} (Diferencia={diff})")
        assert c_lone == 0, f"Lonestar tiene jugadores: {c_lone}"
        assert c_mant + c_valk == 40, f"Jugadores totales cambiaron: {c_mant + c_valk}"
        assert diff <= 6, f"¡ERROR! La diferencia es {diff} > 6 en calentamiento!"
        print(f"  ✅ PASO 1 EXITOSO: La diferencia {diff} <= 6 fue respetada inmediatamente!")

        # -------------------------------------------------------------
        # 2. ESCENARIO: CAMBIO MASIVO DE EQUIPO DURANTE EL INICIO (< 10s)
        #    Jugadores intentan cambiar de bando (Team Hopping)
        # -------------------------------------------------------------
        print("\n[PASO 2] Simulación: Team hopping masivo durante el inicio (<10s)")
        await client.post(f"{MOCK_URL}/mock/set_match_seconds?seconds=6")
        
        # Obtenemos los que están en Valkyra actualmente
        current_valk = [p for p in pl_resp if p["faction"].lower().startswith("valk")]
        # 6 de ellos intentan cambiarse a Manticore
        for p in current_valk[:6]:
            sid = p["steamId"]
            await client.post(f"{MOCK_URL}/v1/players/{sid}/faction", json={"faction": "Manticore"}, headers=RCON_AUTH)
        
        print(f"  * 6 jugadores de Valkyra cambiaron manualmente su facción a Manticore.")
        print("  * Esperando 7.5 segundos para que el bot detecte y revierta el team switch...")
        await asyncio.sleep(7.5)

        pl_resp2 = (await client.get(f"{MOCK_URL}/v1/players", headers=RCON_AUTH)).json()["players"]
        c_mant2 = sum(1 for p in pl_resp2 if p["faction"].lower().startswith("mant"))
        c_valk2 = sum(1 for p in pl_resp2 if p["faction"].lower().startswith("valk"))
        diff2 = abs(c_mant2 - c_valk2)
        print(f"  * Resultado tras ARMA Lock: Manticore={c_mant2}, Valkyra={c_valk2} (Diferencia={diff2})")
        assert diff2 <= 6, f"¡ERROR! La diferencia tras hopping es {diff2} > 6!"
        print(f"  ✅ PASO 2 EXITOSO: ARMA Lock y balance mantuvieron la diferencia en {diff2} <= 6!")

        # -------------------------------------------------------------
        # 3. ESCENARIO: GENTE ENTRANDO AL AZUL (LONESTAR)
        #    12 jugadores se conectan a Lonestar
        # -------------------------------------------------------------
        print("\n[PASO 3] Simulación: 12 jugadores nuevos entran a Lonestar (Azul)")
        players_p3 = list(pl_resp2)
        for i in range(1, 13):
            players_p3.append({
                "name": f"BlueGuy_{i}",
                "steamId": f"7656119830000{i:04d}",
                "faction": "Lonestar",
                "kills": 0,
                "deaths": 0,
                "cash": 0,
                "pingMs": 40
            })
        await client.post(f"{MOCK_URL}/mock/set_players", json=players_p3)
        print(f"  * 12 jugadores inyectados en Lonestar (Total jugadores = {len(players_p3)})")
        print("  * Esperando 7.5 segundos para que Lonestar sea vaciado...")
        await asyncio.sleep(7.5)

        pl_resp3 = (await client.get(f"{MOCK_URL}/v1/players", headers=RCON_AUTH)).json()["players"]
        c_mant3 = sum(1 for p in pl_resp3 if p["faction"].lower().startswith("mant"))
        c_valk3 = sum(1 for p in pl_resp3 if p["faction"].lower().startswith("valk"))
        c_lone3 = sum(1 for p in pl_resp3 if p["faction"].lower().startswith("lone"))
        diff3 = abs(c_mant3 - c_valk3)
        print(f"  * Resultado tras vaciado de Lonestar: Manticore={c_mant3}, Valkyra={c_valk3}, Lonestar={c_lone3} (Diferencia={diff3})")
        assert c_lone3 == 0, f"¡ERROR! Quedaron {c_lone3} jugadores en Lonestar!"
        assert len(pl_resp3) == 52, f"Total de jugadores no coincide: {len(pl_resp3)}"
        assert diff3 <= 6, f"¡ERROR! Diferencia {diff3} > 6 tras vaciar Lonestar!"
        print(f"  ✅ PASO 3 EXITOSO: Lonestar drenado a 0 y jugadores repartidos equitativamente!")

        # -------------------------------------------------------------
        # 4. ESCENARIO: FLUJO DE GENTE DURANTE LA PARTIDA (> 10s)
        #    Ragequit de 15 jugadores en Valkyra durante combate activo
        # -------------------------------------------------------------
        print("\n[PASO 4] Simulación: Ragequit masivo en Valkyra durante la partida (match_seconds=250)")
        await client.post(f"{MOCK_URL}/mock/set_match_seconds?seconds=250")

        # Asignamos estadísticas a los jugadores de Manticore: algunos veteranos con mucho cash y kills, otros nuevos con 0
        current_m = [p for p in pl_resp3 if p["faction"].lower().startswith("mant")]
        for idx, p in enumerate(current_m):
            if idx < 10:
                p["cash"] = 80000  # veterano con vehículo
                p["kills"] = 15
            else:
                p["cash"] = 0      # recién entrado
                p["kills"] = 0

        # Removemos 15 jugadores de Valkyra (ragequit)
        current_v = [p for p in pl_resp3 if p["faction"].lower().startswith("valk")]
        remaining_v = current_v[:-15]
        print(f"  * Ragequit: Valkyra baja de {len(current_v)} a {len(remaining_v)} jugadores. Manticore tiene {len(current_m)}.")
        
        await client.post(f"{MOCK_URL}/mock/set_players", json=current_m + remaining_v)
        print("  * Esperando 7.5 segundos para que el autobalance en partida reequilibre...")
        await asyncio.sleep(7.5)

        pl_resp4 = (await client.get(f"{MOCK_URL}/v1/players", headers=RCON_AUTH)).json()["players"]
        c_mant4 = sum(1 for p in pl_resp4 if p["faction"].lower().startswith("mant"))
        c_valk4 = sum(1 for p in pl_resp4 if p["faction"].lower().startswith("valk"))
        diff4 = abs(c_mant4 - c_valk4)
        print(f"  * Resultado tras rebalanceo en partida: Manticore={c_mant4}, Valkyra={c_valk4} (Diferencia={diff4})")
        assert diff4 <= 6, f"¡ERROR! Diferencia en partida {diff4} > 6!"
        
        # Verificar que los veteranos de Manticore (cash=80000) NO fueron movidos
        for p in pl_resp4:
            if p.get("cash", 0) >= 80000:
                assert p["faction"].lower().startswith("mant"), f"¡ERROR! Veterano {p['name']} con cash {p['cash']} fue transferido indebidamente!"
        print("  ✅ PASO 4 EXITOSO: Rebalanceo activo funcionó y los jugadores con cash/vehículos fueron protegidos!")

        # -------------------------------------------------------------
        # 5. ESCENARIO: INTENTO DE SUPERAR 50 JUGADORES (HARD CAP 50v50)
        #    Inyectamos 70 Manticore vs 30 Valkyra
        # -------------------------------------------------------------
        print("\n[PASO 5] Simulación: Intento de superar el tope (70 Manticore vs 30 Valkyra)")
        cap_players = []
        for i in range(1, 71):
            cap_players.append({
                "name": f"CapMant_{i}",
                "steamId": f"7656119840000{i:04d}",
                "faction": "Manticore",
                "kills": 0,
                "deaths": 0,
                "cash": 0,
                "pingMs": 25
            })
        for i in range(1, 31):
            cap_players.append({
                "name": f"CapValk_{i}",
                "steamId": f"7656119850000{i:04d}",
                "faction": "Valkyre",
                "kills": 0,
                "deaths": 0,
                "cash": 0,
                "pingMs": 25
            })
        
        await client.post(f"{MOCK_URL}/mock/set_players", json=cap_players)
        print("  * Servidor inyectado con 70 Manticore y 30 Valkyra (Total 100 jugadores).")
        print("  * Esperando 7.5 segundos para que la regla de Cap de 50 transfiera los 20 excedentes...")
        await asyncio.sleep(7.5)

        pl_resp5 = (await client.get(f"{MOCK_URL}/v1/players", headers=RCON_AUTH)).json()["players"]
        c_mant5 = sum(1 for p in pl_resp5 if p["faction"].lower().startswith("mant"))
        c_valk5 = sum(1 for p in pl_resp5 if p["faction"].lower().startswith("valk"))
        c_lone5 = sum(1 for p in pl_resp5 if p["faction"].lower().startswith("lone"))
        print(f"  * Resultado tras Cap de 50: Manticore={c_mant5}, Valkyra={c_valk5}, Lonestar={c_lone5}")
        assert c_mant5 <= 50, f"¡ERROR! Manticore superó el límite de 50: {c_mant5}"
        assert c_valk5 <= 50, f"¡ERROR! Valkyra superó el límite de 50: {c_valk5}"
        assert c_mant5 == 50 and c_valk5 == 50, f"¡ERROR! No es 50v50 perfecto: {c_mant5} vs {c_valk5}"
        print("  ✅ PASO 5 EXITOSO: ¡Cap estricto de 50 jugadores logrado perfectamente (50 vs 50)!")

        # -------------------------------------------------------------
        # 6. ESCENARIO: PERSISTENCIA TRAS REINICIO DE PARTIDA (NEXT MATCH)
        # -------------------------------------------------------------
        print("\n[PASO 6] Simulación: Reinicio de partida / Siguiente mapa")
        nxt = (await client.post(f"{MOCK_URL}/mock/next_match")).json()
        print(f"  * Siguiente partida forzada en RCON: {nxt}")
        print("  * Esperando 7.5 segundos para que el bot detecte la nueva partida...")
        await asyncio.sleep(7.5)

        db_state_after = check_db()
        print(f"  * Estado en DB Postgres: {db_state_after}")
        assert db_state_after.get("MODE_50V50_STATE") == "active", f"¡ERROR! El estado en DB se reseteó: {db_state_after}"

        status_api = (await client.get(f"{API_URL}/v1/mode50v50", headers=API_HEADERS)).json()
        print(f"  * Estado en API /v1/mode50v50: {status_api}")
        assert status_api.get("state") == "active", f"API status no es active: {status_api}"
        print("  ✅ PASO 6 EXITOSO: El estado se mantiene activo en DB y API a través de cambios de mapa!")


        # Limpiar al finalizar
        await client.post(f"{MOCK_URL}/mock/reset_players")

    print("\n" + "=" * 80)
    print("🎉 TODAS LAS PRUEBAS EN VIVO CONTRA LOS 4 CONTENEDORES PASARON AL 100%")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(run_stress_suite())
