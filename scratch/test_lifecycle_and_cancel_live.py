import asyncio
import httpx
import subprocess

API_BASE = "http://localhost:8000/api/v1"
HEADERS = {"X-API-Key": "local-api-key"}
MOCK_BASE = "http://localhost:9001"

def query_db_config():
    cmd = [
        "docker", "exec", "matefield_db_local",
        "psql", "-U", "matefield_user", "-d", "matefield_db", "-t", "-A", "-F", "=",
        "-c", "SELECT config_key, config_value FROM bot_config WHERE config_key LIKE 'MODE_50V50%';"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    out = {}
    for line in res.stdout.strip().splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out

def reset_db_inactive():
    cmd = [
        "docker", "exec", "matefield_db_local",
        "psql", "-U", "matefield_user", "-d", "matefield_db",
        "-c", "INSERT INTO bot_config (config_key, config_value) VALUES ('MODE_50V50_STATE', 'inactive') ON CONFLICT (config_key) DO UPDATE SET config_value = 'inactive'; INSERT INTO bot_config (config_key, config_value) VALUES ('MODE_50V50_ENABLED', 'false') ON CONFLICT (config_key) DO UPDATE SET config_value = 'false';"
    ]
    subprocess.run(cmd, capture_output=True, text=True, check=True)

async def main():
    print("=================================================================")
    print("[TEST] CICLO DE VIDA DIFERIDO Y CANCELACION DEL MODO 50v50")
    print("=================================================================\n")

    reset_db_inactive()

    async with httpx.AsyncClient() as client:
        # Step 0: Ensure inactive start
        print("> [Paso 0] Asegurar estado inicial inactivo")
        db = query_db_config()
        print(f"   DB state: {db}")

        r_status = await client.get(f"{API_BASE}/mode50v50", headers=HEADERS)
        st_data = r_status.json()
        print(f"   API status: state={st_data.get('state')}, enabled={st_data.get('enabled')}")
        assert st_data.get("state") == "inactive"
        assert st_data.get("enabled") is False
        print("   [OK] Estado inicial INACTIVO verificado con exito.\n")

        # Step 1: Schedule enable (pending_enable)
        print("> [Paso 1] Ejecutar /mode50v50 enable desde estado inactivo")
        r_en = await client.post(f"{API_BASE}/mode50v50/enable", headers=HEADERS)
        en_data = r_en.json()
        print(f"   API enable: {en_data}")
        assert en_data.get("ok") is True
        assert en_data.get("state") == "pending_enable", f"Esperaba pending_enable, obtuvo {en_data.get('state')}"
        assert en_data.get("enabled") is False, "En pending_enable no debe estar habilitado aun"

        db = query_db_config()
        print(f"   DB post-enable: {db}")
        assert db.get("MODE_50V50_STATE") == "pending_enable"
        assert db.get("MODE_50V50_ENABLED") == "false"
        print("   [OK] Modo programado para la siguiente partida (pending_enable) verificado.\n")

        # Step 2: Verify mode_50v50_loop does NOT auto-promote mid-match
        print("> [Paso 2] Esperar 8s (mas que el loop de 6s) para verificar que NO se auto-activa a mitad de partida")
        await asyncio.sleep(8)
        db = query_db_config()
        print(f"   DB tras 8s de juego: {db}")
        assert db.get("MODE_50V50_STATE") == "pending_enable", f"¡ERROR! Se auto-promovio en la misma partida: {db}"
        assert db.get("MODE_50V50_ENABLED") == "false"
        print("   [OK] El bot respeto la partida en curso y permanecio en pending_enable sin tocar jugadores.\n")

        # Step 3: Cancel pending activation
        print("> [Paso 3] Cancelar activacion programada con /mode50v50/cancel")
        r_cancel = await client.post(f"{API_BASE}/mode50v50/cancel", headers=HEADERS)
        cancel_data = r_cancel.json()
        print(f"   API cancel: {cancel_data}")
        assert cancel_data.get("ok") is True
        assert cancel_data.get("state") == "inactive"
        assert cancel_data.get("enabled") is False

        db = query_db_config()
        print(f"   DB post-cancel: {db}")
        assert db.get("MODE_50V50_STATE") == "inactive"
        assert db.get("MODE_50V50_ENABLED") == "false"
        print("   [OK] Cancelacion de activacion verificada con exito (revertido a inactive).\n")

        # Step 4: Schedule enable again
        print("> [Paso 4] Volver a programar activacion para la siguiente partida")
        r_en2 = await client.post(f"{API_BASE}/mode50v50/enable", headers=HEADERS)
        assert r_en2.json().get("state") == "pending_enable"
        print("   [OK] Estado pending_enable establecido.\n")

        # Step 5: Simulate match rotation to trigger transition to ACTIVE
        print("> [Paso 5] Simular cambio de partida en Mock RCON (/mock/next_match)")
        r_rot = await client.post(f"{MOCK_BASE}/mock/next_match")
        print(f"   Mock next_match: {r_rot.json()}")
        print("   Esperando que sync_engine (poll_rcon) detecte la nueva partida (hasta 15s)...")
        db = {}
        for _ in range(15):
            await asyncio.sleep(1)
            db = query_db_config()
            if db.get("MODE_50V50_STATE") == "active":
                break

        print(f"   DB post-rotacion: {db}")
        assert db.get("MODE_50V50_STATE") == "active", f"Esperaba active en nueva partida, obtuvo: {db}"
        assert db.get("MODE_50V50_ENABLED") == "true"

        r_st = await client.get(f"{API_BASE}/mode50v50", headers=HEADERS)
        print(f"   API status en nueva partida: {r_st.json()}")
        assert r_st.json().get("state") == "active"
        assert r_st.json().get("enabled") is True
        print("   [OK] Transicion automatica a ACTIVE al iniciar la nueva partida verificada.\n")

        # Step 6: Schedule disable while active (pending_disable)
        print("> [Paso 6] Ejecutar /mode50v50 disable mientras esta ACTIVO")
        r_dis = await client.post(f"{API_BASE}/mode50v50/disable", headers=HEADERS)
        dis_data = r_dis.json()
        print(f"   API disable: {dis_data}")
        assert dis_data.get("ok") is True
        assert dis_data.get("state") == "pending_disable"
        assert dis_data.get("enabled") is True, "Durante la partida actual debe seguir habilitado"

        db = query_db_config()
        print(f"   DB post-disable: {db}")
        assert db.get("MODE_50V50_STATE") == "pending_disable"
        assert db.get("MODE_50V50_ENABLED") == "true"
        print("   [OK] Desactivacion PROGRAMADA para la siguiente partida (pending_disable) verificada.\n")

        # Step 7: Cancel pending deactivation (revert to active)
        print("> [Paso 7] Cancelar desactivacion programada con /mode50v50/cancel")
        r_cancel2 = await client.post(f"{API_BASE}/mode50v50/cancel", headers=HEADERS)
        cancel2_data = r_cancel2.json()
        print(f"   API cancel: {cancel2_data}")
        assert cancel2_data.get("ok") is True
        assert cancel2_data.get("state") == "active"
        assert cancel2_data.get("enabled") is True

        db = query_db_config()
        print(f"   DB post-cancel deactivation: {db}")
        assert db.get("MODE_50V50_STATE") == "active"
        assert db.get("MODE_50V50_ENABLED") == "true"
        print("   [OK] Cancelacion de desactivacion verificada con exito (mantuvo ACTIVE).\n")

        # Step 8: Schedule disable again and verify new match transitions to INACTIVE
        print("> [Paso 8] Programar desactivacion nuevamente")
        r_dis2 = await client.post(f"{API_BASE}/mode50v50/disable", headers=HEADERS)
        assert r_dis2.json().get("state") == "pending_disable"

        print("> [Paso 9] Simular segundo cambio de partida en Mock RCON")
        await client.post(f"{MOCK_BASE}/mock/next_match")
        print("   Esperando que sync_engine detecte la nueva partida (hasta 15s)...")
        db = {}
        for _ in range(15):
            await asyncio.sleep(1)
            db = query_db_config()
            if db.get("MODE_50V50_STATE") == "inactive":
                break

        print(f"   DB post-segunda rotacion: {db}")
        assert db.get("MODE_50V50_STATE") == "inactive", f"Esperaba inactive en nueva partida, obtuvo: {db}"
        assert db.get("MODE_50V50_ENABLED") == "false"

        r_st_final = await client.get(f"{API_BASE}/mode50v50", headers=HEADERS)
        print(f"   API status final: {r_st_final.json()}")
        assert r_st_final.json().get("state") == "inactive"
        assert r_st_final.json().get("enabled") is False
        print("   [OK] Transicion automatica a INACTIVE al terminar la partida verificada.\n")

        # Step 10: Cancel when nothing is pending
        print("> [Paso 10] Intentar cancelar cuando no hay nada pendiente")
        r_noop = await client.post(f"{API_BASE}/mode50v50/cancel", headers=HEADERS)
        noop_data = r_noop.json()
        print(f"   API cancel no-op: {noop_data}")
        assert noop_data.get("ok") is False
        print("   [OK] Rechazo de cancelacion sin tareas pendientes verificado.\n")

    print("=================================================================")
    print("[EXITO] TODAS LAS PRUEBAS DE CICLO DE VIDA Y CANCELACION PASARON (10/10)")
    print("=================================================================")

if __name__ == "__main__":
    asyncio.run(main())
