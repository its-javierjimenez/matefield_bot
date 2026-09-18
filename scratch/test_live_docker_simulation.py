import asyncio
import httpx
import sys

API_BASE = "http://localhost:8000"
MOCK_BASE = "http://localhost:9001"
API_KEY = "local-api-key"
RCON_AUTH = "Bearer test"

async def main():
    print("=" * 70)
    print(" EJECUTANDO TEST CONTRA DOCKER MOCK_RCON CON SIMULACIÓN ACTIVA")
    print("=" * 70)

    headers_api = {"X-API-Key": API_KEY}
    headers_rcon = {"Authorization": RCON_AUTH}

    async with httpx.AsyncClient(timeout=20.0) as client:
        # 1. Verificar conectividad básica con ambos contenedores
        print("\n--- 1. Comprobación de Contenedores en Docker ---")
        st_rcon = (await client.get(f"{MOCK_BASE}/v1/status", headers=headers_rcon)).json()
        print(f"  * Mock RCON vivo: Mapa={st_rcon['map']}, ScoreTick={st_rcon['scoreTick']['current']}, MatchSec={st_rcon['matchSeconds']}")
        
        st_api = (await client.get(f"{API_BASE}/api/v1/mode50v50", headers=headers_api)).json()
        print(f"  * API RCON vivo: Estado 50v50 inicial = {st_api}")

        # Asegurar estado inactivo
        await client.post(f"{API_BASE}/api/v1/mode50v50/disable", headers=headers_api)
        # Forzar siguiente partida para que cualquier pending_disable se consolide en inactive
        await client.post(f"{MOCK_BASE}/mock/next_match")
        await asyncio.sleep(4)
        # Si todavía no está inactivo, forzar disable de nuevo
        await client.post(f"{API_BASE}/api/v1/mode50v50/disable", headers=headers_api)
        await client.post(f"{MOCK_BASE}/mock/reset_players")
        
        # Esperar a que el estado sea inactive
        for _ in range(10):
            st = (await client.get(f"{API_BASE}/api/v1/mode50v50", headers=headers_api)).json()
            if st["state"] == "inactive":
                break
            await asyncio.sleep(1)
        
        # 2. Ejecutar /mode50v50 enable a mitad de partida
        print("\n--- 2. Comando /mode50v50 enable (Activación Diferida) ---")
        en_res = (await client.post(f"{API_BASE}/api/v1/mode50v50/enable", headers=headers_api)).json()
        print(f"  * Respuesta API: {en_res}")
        assert en_res["state"] == "pending_enable", f"Esperaba pending_enable, obtuve {en_res['state']}"
        assert en_res["enabled"] is False, "enabled debe ser False mientras la partida actual sigue en curso"

        # Verificar que ServerSettings.ini en RCON ya tiene bLockOverpopulatedTeamsConfig=false
        cfg = (await client.get(f"{MOCK_BASE}/v1/config", headers=headers_rcon)).json()
        assert "bLockOverpopulatedTeamsConfig=false" in cfg["text"], "RCON debió recibir bLockOverpopulatedTeamsConfig=false"
        print("  * Verificado: RCON config actualizada (Unreal Engine team balancing = OFF).")

        # Verificar broadcast previo
        audit = (await client.get(f"{MOCK_BASE}/v1/audit?limit=5", headers=headers_rcon)).json()
        bc_found = any("En la siguiente partida se activara el modo 50v50" in e["detail"] for e in audit["entries"])
        assert bc_found, "Broadcast de programación no encontrado en audit logs de RCON"
        print("  * Verificado: Broadcast 'En la siguiente partida se activara el modo 50v50' emitido a jugadores.")

        # Esperar 8 segundos para comprobar que la partida actual NO fue alterada
        print("  * Esperando 8 segundos para validar que la partida actual NO es tocada...")
        await asyncio.sleep(8)
        cur_status = (await client.get(f"{API_BASE}/api/v1/mode50v50", headers=headers_api)).json()
        assert cur_status["state"] == "pending_enable"
        assert cur_status["enabled"] is False
        print("  -> CONFIRMADO: La partida actual sigue normal sin cortes.")

        # 3. Avanzar a la siguiente partida (Simulación de cambio de mapa/rotación)
        print("\n--- 3. Fin de partida y transición automática a 50v50 ---")
        nxt = (await client.post(f"{MOCK_BASE}/mock/next_match")).json()
        print(f"  * Siguiente mapa forzado en Mock RCON: {nxt['map']} (Rotación {nxt['new_rotation']})")

        # Esperar a que sync_engine (polling cada 6-10s) detecte la transición
        print("  * Esperando hasta 15s para que sync_engine detecte el nuevo mapa y active 50v50...")
        activated = False
        for attempt in range(15):
            await asyncio.sleep(1)
            st_check = (await client.get(f"{API_BASE}/api/v1/mode50v50", headers=headers_api)).json()
            if st_check["state"] == "active" and st_check["enabled"] is True:
                activated = True
                print(f"  * ¡Transición exitosa al segundo {attempt + 1}! Estado: {st_check}")
                break

        assert activated, "sync_engine no transicionó pending_enable a active en el nuevo mapa!"

        # Verificar broadcast de activación
        audit = (await client.get(f"{MOCK_BASE}/v1/audit?limit=5", headers=headers_rcon)).json()
        bc_active = any("Modo 50v50 ACTIVADO para esta partida" in e["detail"] for e in audit["entries"])
        assert bc_active, "Broadcast 'Modo 50v50 ACTIVADO...' debió registrarse en RCON"
        print("  * Verificado: Broadcast de activación recibido por los jugadores en el servidor.")

        # 4. Prueba de balanceo de 100 jugadores concurrentes en Docker
        print("\n--- 4. Seeding de 100 jugadores y autobalanceo 50v50 en vivo ---")
        seed_res = (await client.post(f"{MOCK_BASE}/mock/seed_full_server?total=100")).json()
        print(f"  * Servidor poblado: Lonestar={seed_res['lonestar']}, Valkyre={seed_res['valkyre']}, Manticore={seed_res['manticore']}")

        print("  * Esperando 12s para que mode_50v50_loop ejecute y drene a los azules...")
        balanced = False
        for attempt in range(15):
            await asyncio.sleep(2)
            pl_resp = (await client.get(f"{MOCK_BASE}/v1/players", headers=headers_rcon)).json()
            pl_list = pl_resp["players"]
            blue = sum(1 for p in pl_list if p.get("faction") == "Lonestar")
            valk = sum(1 for p in pl_list if p.get("faction") == "Valkyre")
            mant = sum(1 for p in pl_list if p.get("faction") == "Manticore")
            print(f"    [T+{attempt*2}s] Azules={blue}, Rojos={valk}, Verdes={mant}")
            if blue == 0 and valk == 50 and mant == 50:
                balanced = True
                print("  * ¡Equilibrio perfecto 50v50 alcanzado en el contenedor!")
                break

        assert balanced, f"No se alcanzó 50v50. Azules={blue}, Valk={valk}, Mant={mant}"

        # 5. Candado ARMA: Intento de cambio manual en mitad de partida
        print("\n--- 5. Prueba de Candado ARMA en vivo ---")
        pl_resp = (await client.get(f"{MOCK_BASE}/v1/players", headers=headers_rcon)).json()
        valk_player = next(p for p in pl_resp["players"] if p.get("faction") == "Valkyre")
        pid = valk_player["steamId"]
        print(f"  * Jugador {valk_player['name']} ({pid}) intenta cambiarse manualmente a Manticore...")
        await client.post(f"{MOCK_BASE}/v1/players/{pid}/faction", json={"faction": "Manticore"}, headers=headers_rcon)

        # Esperar a que el loop detecte el cambio no autorizado y lo revierta
        print("  * Esperando que el bot lo detecte y revierta...")
        reverted = False
        for attempt in range(15):
            await asyncio.sleep(2)
            pl_resp = (await client.get(f"{MOCK_BASE}/v1/players", headers=headers_rcon)).json()
            target_p = next(p for p in pl_resp["players"] if p["steamId"] == pid)
            if target_p["faction"] == "Valkyre":
                reverted = True
                print(f"  * ¡Revertido con éxito a Valkyre en el intento {attempt+1}! Facción actual: {target_p['faction']}")
                break

        assert reverted, "Candado ARMA falló: el jugador no fue revertido a su equipo original."

        # 6. Desactivación diferida durante partida en curso
        print("\n--- 6. Comando /mode50v50 disable durante partida activa ---")
        dis_res = (await client.post(f"{API_BASE}/api/v1/mode50v50/disable", headers=headers_api)).json()
        print(f"  * Respuesta API: {dis_res}")
        assert dis_res["state"] == "pending_disable"
        assert dis_res["enabled"] is True, "50v50 debe mantenerse activo hasta que concluya el mapa actual"

        # Verificar broadcast de desactivación programada
        audit = (await client.get(f"{MOCK_BASE}/v1/audit?limit=5", headers=headers_rcon)).json()
        bc_dis = any("En la siguiente partida se desactivara el modo 50v50" in e["detail"] for e in audit["entries"])
        assert bc_dis, "Broadcast 'En la siguiente partida se desactivara el modo 50v50' debió registrarse"
        print("  * Verificado: Broadcast de fin programado emitido a jugadores.")

        # Verificar restauración de bLockOverpopulatedTeamsConfig=true
        cfg = (await client.get(f"{MOCK_BASE}/v1/config", headers=headers_rcon)).json()
        assert "bLockOverpopulatedTeamsConfig=true" in cfg["text"]
        print("  * Verificado: RCON config restauró team balancing con threshold 1.")

        # 7. Fin de partida tras desactivación -> Volver a 33v33v33
        print("\n--- 7. Fin de partida -> Vuelta automática a 33v33v33 ---")
        await client.post(f"{MOCK_BASE}/mock/next_match")
        deactivated = False
        for attempt in range(20):
            await asyncio.sleep(1)
            st_check = (await client.get(f"{API_BASE}/api/v1/mode50v50", headers=headers_api)).json()
            if st_check["state"] == "inactive" and st_check["enabled"] is False:
                deactivated = True
                print(f"  * ¡Vuelta a modo normal al segundo {attempt + 1}! Estado: {st_check}")
                break

        assert deactivated, "sync_engine no regresó a inactive en el nuevo mapa!"

        # Verificar broadcast final
        audit = (await client.get(f"{MOCK_BASE}/v1/audit?limit=5", headers=headers_rcon)).json()
        bc_fin = any("Modo 50v50 FINALIZADO" in e["detail"] for e in audit["entries"])
        assert bc_fin, "Broadcast 'Modo 50v50 FINALIZADO' debió emitirse"
        print("  * Verificado: Broadcast 'Modo 50v50 FINALIZADO. Volviendo a 33v33v33.' confirmado.")

        # Limpiar
        await client.post(f"{MOCK_BASE}/mock/reset_players")

    print("\n" + "=" * 70)
    print(" [ÉXITO TOTAL] TODAS LAS PRUEBAS EN VIVO CONTRA DOCKER PASARON AL 100%")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(main())
