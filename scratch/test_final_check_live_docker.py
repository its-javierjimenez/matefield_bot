import asyncio
import httpx
import sys
import time

API_BASE = "http://localhost:8000"
MOCK_BASE = "http://localhost:9001"
API_KEY = "local-api-key"
RCON_AUTH = "Bearer test"

async def main():
    print("=" * 80)
    print(" [FINAL CHECK] EN VIVO CONTRA DOCKER MOCK RCON Y API RCON")
    print("=" * 80)

    headers_api = {"X-API-Key": API_KEY}
    headers_rcon = {"Authorization": RCON_AUTH}

    async with httpx.AsyncClient(timeout=30.0) as client:
        # ---------------------------------------------------------------------
        # 0. ESTADO INICIAL
        # ---------------------------------------------------------------------
        print("\n--- [CHECK 0] Limpieza y Comprobación Inicial ---")
        # Asegurar estado limpio inactivo
        await client.post(f"{API_BASE}/api/v1/mode50v50/disable", headers=headers_api)
        await client.post(f"{MOCK_BASE}/mock/next_match")
        await asyncio.sleep(2)
        await client.post(f"{API_BASE}/api/v1/mode50v50/disable", headers=headers_api)
        await client.post(f"{MOCK_BASE}/mock/reset_players")
        
        st_init = (await client.get(f"{API_BASE}/api/v1/mode50v50", headers=headers_api)).json()
        print(f"  * Estado inicial 50v50: {st_init['state']} (enabled={st_init['enabled']})")
        assert st_init["state"] == "inactive"
        assert st_init["enabled"] is False

        cfg_init = (await client.get(f"{MOCK_BASE}/v1/config", headers=headers_rcon)).json()
        assert "bLockOverpopulatedTeamsConfig=true" in cfg_init["text"]
        print("  * RCON inicial: bLockOverpopulatedTeamsConfig=true verificado.")
        print("  -> CHECK 0 SUPERADO: Entorno completamente limpio.")

        # ---------------------------------------------------------------------
        # 1. PROGRAMAR ACTIVACIÓN EN PLENA PARTIDA (/mode50v50 enable)
        # ---------------------------------------------------------------------
        print("\n--- [CHECK 1] Programar Activación: /mode50v50 enable ---")
        en_res = (await client.post(f"{API_BASE}/api/v1/mode50v50/enable", headers=headers_api)).json()
        print(f"  * Respuesta: state={en_res['state']}, enabled={en_res['enabled']}")
        assert en_res["state"] == "pending_enable"
        assert en_res["enabled"] is False

        # Configuración en RCON ServerSettings.ini
        cfg = (await client.get(f"{MOCK_BASE}/v1/config", headers=headers_rcon)).json()
        assert "bLockOverpopulatedTeamsConfig=false" in cfg["text"]
        print("  * RCON ServerSettings.ini: bLockOverpopulatedTeamsConfig=false inyectado.")

        # Broadcast a los jugadores
        audit = (await client.get(f"{MOCK_BASE}/v1/audit?limit=5", headers=headers_rcon)).json()
        assert any("En la siguiente partida se activara el modo 50v50" in e["detail"] for e in audit["entries"])
        print("  * Broadcast emitido: 'Modo 50v50: En la siguiente partida se activara el modo 50v50'")
        print("  -> CHECK 1 SUPERADO: Activación diferida programada sin tocar la partida actual.")

        # ---------------------------------------------------------------------
        # 2. CANCELACIÓN DE ACTIVACIÓN PROGRAMADA (/mode50v50 disable antes de que empiece)
        # ---------------------------------------------------------------------
        print("\n--- [CHECK 2] Cancelar Activación Programada: /mode50v50 disable ---")
        cancel_res = (await client.post(f"{API_BASE}/api/v1/mode50v50/disable", headers=headers_api)).json()
        print(f"  * Respuesta cancelación: state={cancel_res['state']}, enabled={cancel_res['enabled']}")
        assert cancel_res["state"] == "inactive"
        assert cancel_res["enabled"] is False

        audit = (await client.get(f"{MOCK_BASE}/v1/audit?limit=5", headers=headers_rcon)).json()
        assert any("Se ha cancelado la activacion, seguiremos normal" in e["detail"] for e in audit["entries"])
        print("  * Broadcast emitido: 'Modo 50v50: Se ha cancelado la activacion, seguiremos normal'")
        print("  -> CHECK 2 SUPERADO: Cancelación inmediata confirmada.")

        # ---------------------------------------------------------------------
        # 3. RE-PROGRAMAR Y DETECCIÓN AUTOMÁTICA DE NUEVA PARTIDA / REINICIO
        # ---------------------------------------------------------------------
        print("\n--- [CHECK 3] Re-programar y Transición Automática a Siguiente Partida ---")
        await client.post(f"{API_BASE}/api/v1/mode50v50/enable", headers=headers_api)
        
        # Forzar transición de mapa/partida
        nxt = (await client.post(f"{MOCK_BASE}/mock/next_match")).json()
        print(f"  * Nueva partida iniciada en servidor: Mapa {nxt['map']} (Rotación {nxt['new_rotation']})")

        # Esperar a que sync_engine detecte y active
        activated = False
        for attempt in range(15):
            await asyncio.sleep(1)
            st = (await client.get(f"{API_BASE}/api/v1/mode50v50", headers=headers_api)).json()
            if st["state"] == "active" and st["enabled"] is True:
                activated = True
                print(f"  * sync_engine detectó y activó 50v50 en el segundo {attempt + 1}!")
                break
        assert activated, "sync_engine no activó 50v50 en la nueva partida"

        audit = (await client.get(f"{MOCK_BASE}/v1/audit?limit=5", headers=headers_rcon)).json()
        assert any("Modo 50v50 ACTIVADO para esta partida" in e["detail"] for e in audit["entries"])
        print("  * Broadcast emitido: 'Modo 50v50 ACTIVADO para esta partida (Rojo vs Verde)!'")
        print("  -> CHECK 3 SUPERADO: Arranque automático impecable.")

        # ---------------------------------------------------------------------
        # 4. PRUEBA DE CARGA: DRENAJE TOTAL DE AZULES Y BALANCEO 50v50
        # ---------------------------------------------------------------------
        print("\n--- [CHECK 4] Prueba de Carga: 100 Jugadores Concurrentes ---")
        seed = (await client.post(f"{MOCK_BASE}/mock/seed_full_server?total=100")).json()
        print(f"  * Población inicial: Lonestar={seed['lonestar']}, Valkyre={seed['valkyre']}, Manticore={seed['manticore']}")

        print("  * Esperando que el loop de balanceo (cada 6s) drene Lonestar y complete 50v50...")
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
                break

        assert balanced, f"Fallo al equilibrar: Lonestar={blue}, Valkyre={valk}, Manticore={mant}"
        print("  * Servidor exactamente en 50 Rojos vs 50 Verdes (0 Azules).")
        print("  -> CHECK 4 SUPERADO: Drenaje y balanceo perfecto con 100 jugadores.")

        # ---------------------------------------------------------------------
        # 5. CANDADO ANTITRAIDORES (ARMA LOCK)
        # ---------------------------------------------------------------------
        print("\n--- [CHECK 5] Candado Antitraidores (ARMA Lock) en Vivo ---")
        pl_resp = (await client.get(f"{MOCK_BASE}/v1/players", headers=headers_rcon)).json()
        valk_player = next(p for p in pl_resp["players"] if p.get("faction") == "Valkyre")
        traitor_sid = valk_player["steamId"]
        print(f"  * Jugador {valk_player['name']} ({traitor_sid}) intenta pasarse de Valkyre a Manticore...")
        await client.post(f"{MOCK_BASE}/v1/players/{traitor_sid}/faction", json={"faction": "Manticore"}, headers=headers_rcon)

        # Esperar a que el loop lo detecte y revierta
        reverted = False
        for attempt in range(15):
            await asyncio.sleep(2)
            pl_resp = (await client.get(f"{MOCK_BASE}/v1/players", headers=headers_rcon)).json()
            p_obj = next(p for p in pl_resp["players"] if p["steamId"] == traitor_sid)
            if p_obj["faction"] == "Valkyre":
                reverted = True
                print(f"  * ¡Revertido con éxito a Valkyre en intento {attempt + 1}! Facción: {p_obj['faction']}")
                break

        assert reverted, "Candado ARMA falló: el traidor no fue devuelto a su equipo"
        audit = (await client.get(f"{MOCK_BASE}/v1/audit?limit=10", headers=headers_rcon)).json()
        whisper_found = any("Cambio de equipo no permitido" in e["detail"] for e in audit["entries"])
        assert whisper_found, "Susurro privado de advertencia al traidor debió enviarse"
        print("  * Susurro privado verificado: 'Cambio de equipo no permitido durante la partida.'")
        print("  -> CHECK 5 SUPERADO: Candado ARMA activo y funcional al 100%.")

        # ---------------------------------------------------------------------
        # 6. CANCELACIÓN DE DESACTIVACIÓN (pending_disable -> active)
        # ---------------------------------------------------------------------
        print("\n--- [CHECK 6] Desactivar y luego Cancelar Desactivación (Seguir en 50v50) ---")
        # Primero programar desactivación
        await client.post(f"{API_BASE}/api/v1/mode50v50/disable", headers=headers_api)
        st_pd = (await client.get(f"{API_BASE}/api/v1/mode50v50", headers=headers_api)).json()
        assert st_pd["state"] == "pending_disable"
        print("  * Estado transicionado a pending_disable.")

        # Ahora el admin se arrepiente y tira /mode50v50 enable
        restore_res = (await client.post(f"{API_BASE}/api/v1/mode50v50/enable", headers=headers_api)).json()
        print(f"  * Respuesta cancelar desactivación: state={restore_res['state']}")
        assert restore_res["state"] == "active"
        assert restore_res["enabled"] is True

        audit = (await client.get(f"{MOCK_BASE}/v1/audit?limit=5", headers=headers_rcon)).json()
        assert any("Se ha cancelado la desactivacion, seguiremos en modo 50v50" in e["detail"] for e in audit["entries"])
        print("  * Broadcast emitido: 'Modo 50v50: Se ha cancelado la desactivacion, seguiremos en modo 50v50'")
        print("  -> CHECK 6 SUPERADO: Cancelación de desactivación restaura el modo 50v50.")

        # ---------------------------------------------------------------------
        # 7. DESACTIVACIÓN PROGRAMADA Y FIN DE PARTIDA -> 33v33v33
        # ---------------------------------------------------------------------
        print("\n--- [CHECK 7] Desactivación Programada y Vuelta Normal a 33v33v33 ---")
        dis_final = (await client.post(f"{API_BASE}/api/v1/mode50v50/disable", headers=headers_api)).json()
        assert dis_final["state"] == "pending_disable"
        assert dis_final["enabled"] is True
        print("  * Desactivación programada para la siguiente partida.")

        # Avanzar mapa para simular fin de partida
        await client.post(f"{MOCK_BASE}/mock/next_match")
        deactivated = False
        for attempt in range(20):
            await asyncio.sleep(1)
            st = (await client.get(f"{API_BASE}/api/v1/mode50v50", headers=headers_api)).json()
            if st["state"] == "inactive" and st["enabled"] is False:
                deactivated = True
                print(f"  * Servidor regresó a modo normal en el segundo {attempt + 1}!")
                break

        assert deactivated, "sync_engine no finalizó el modo 50v50 en el nuevo mapa"
        audit = (await client.get(f"{MOCK_BASE}/v1/audit?limit=5", headers=headers_rcon)).json()
        assert any("Modo 50v50 FINALIZADO" in e["detail"] for e in audit["entries"])
        print("  * Broadcast emitido: 'Modo 50v50 FINALIZADO. Volviendo a 33v33v33.'")

        cfg_final = (await client.get(f"{MOCK_BASE}/v1/config", headers=headers_rcon)).json()
        assert "bLockOverpopulatedTeamsConfig=true" in cfg_final["text"]
        print("  * RCON ServerSettings.ini: bLockOverpopulatedTeamsConfig=true restaurado.")
        print("  -> CHECK 7 SUPERADO: Vuelta normal y limpia a 33v33v33.")

        # Reset final de jugadores
        await client.post(f"{MOCK_BASE}/mock/reset_players")

    print("\n" + "=" * 80)
    print(" [FINAL CHECK TOTALMENTE SUPERADO] TODOS LOS CONTENEDORES Y FUNCIONES AL 100%")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())
