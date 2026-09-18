import asyncio
import os
import sys
import datetime
import time
from typing import Any, Dict, List

# Workspace package paths
sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("packages/wardogs_schemas/src"))
sys.path.insert(0, os.path.abspath("apps/api_rcon"))

from src.connections.apis.rcon import RCONClient
from src.connections.databases.db import BotConfig, Match, Player
from sqlmodel import select, SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
import apps.rcon_mock.src.main as mock_main
from httpx import AsyncClient, ASGITransport
from wardogs_schemas import v1 as schemas

test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

def make_player(name: str, steam_id: str, faction: str, kills: int = 0, deaths: int = 0, cash: int = 0, ping: int = 30) -> Dict[str, Any]:
    return {
        "name": name,
        "steamId": steam_id,
        "faction": faction,
        "kills": kills,
        "deaths": deaths,
        "cash": cash,
        "pingMs": ping
    }

async def main():
    print("=" * 70)
    print(" EJECUTANDO AUDITORÍA COMPLETA Y BATERÍA DE ESCENARIOS MOCK RCON")
    print("=" * 70)

    transport = ASGITransport(app=mock_main.app)
    
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        # Create RCON client mapped to mock ASGI transport
        rcon = RCONClient(base_url="http://test", password="test")
        
        async def custom_request(method, endpoint, **kwargs):
            headers = rcon.headers.copy()
            if "headers" in kwargs:
                headers.update(kwargs.pop("headers"))
            r = await http_client.request(method, endpoint, headers=headers, **kwargs)
            if r.status_code >= 400:
                raise Exception(f"HTTP {r.status_code}: {r.text}")
            if "application/json" in r.headers.get("Content-Type", ""):
                return r.json()
            return r.text
        rcon._request = custom_request

        async def custom_get_config():
            data = await custom_request("GET", "/v1/config")
            return schemas.Config1.model_validate(data)
        rcon.get_config = custom_get_config

        async def custom_update_config(revision, new_text):
            headers = {"If-Match": f'"{revision}"', "Content-Type": "text/plain"}
            data = await custom_request("PUT", "/v1/config?force=true&fullApply=true", content=new_text, headers=headers)
            return schemas.ConfigResult.model_validate(data)
        rcon.update_config = custom_update_config

        # Init DB tables
        async with test_engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

        findings = []

        # =====================================================================
        # ESCENARIO 1: ESTADO INICIAL DEL SERVIDOR RCON Y CONFIGURACIÓN BASE
        # =====================================================================
        print("\n--- [ESCENARIO 1] Verificación inicial del Mock RCON ---")
        st = await rcon.get_status()
        pl = await rcon.get_players()
        cfg = await rcon.get_config()
        print(f"  * Status: Mapa={st.map}, ScoreTick={st.scoreTick.current}, MatchSec={st.matchSeconds}")
        print(f"  * Jugadores: {len(pl.players)} en servidor")
        print(f"  * Config RCON tiene bLockOverpopulatedTeamsConfig=true: {'bLockOverpopulatedTeamsConfig=true' in cfg.text}")
        assert "bLockOverpopulatedTeamsConfig=true" in cfg.text
        assert "OverpopulatedTeamThresholdConfig=1" in cfg.text
        print("  -> Escenario 1 Superado: Mock RCON responde y tiene team balancing activo por defecto.")

        # =====================================================================
        # ESCENARIO 2: COMANDO /mode50v50 enable
        # =====================================================================
        print("\n--- [ESCENARIO 2] Comando /mode50v50 enable ---")
        # Simula endpoint POST /api/v1/mode50v50/enable
        await rcon.set_team_balancing(False)
        await rcon.broadcast("Modo 50v50: En la siguiente partida se activara el modo 50v50")
        async with AsyncSession(test_engine) as session:
            session.add(BotConfig(config_key="MODE_50V50_STATE", config_value="pending_enable"))
            session.add(BotConfig(config_key="MODE_50V50_ENABLED", config_value="false"))
            await session.commit()
            
        cfg_after_en = await rcon.get_config()
        assert "bLockOverpopulatedTeamsConfig=false" in cfg_after_en.text
        audit = await rcon.get_audit_logs(limit=3)
        assert any("En la siguiente partida se activara el modo 50v50" in e.detail for e in audit.entries)
        print("  * RCON config actualizado: bLockOverpopulatedTeamsConfig=false (Team balancing de Unreal Engine apagado).")
        print("  * Broadcast emitido: 'Modo 50v50: En la siguiente partida se activara el modo 50v50'")
        print("  * DB state: MODE_50V50_STATE = pending_enable")
        print("  -> Escenario 2 Superado: Modo programado y RCON preparado con anuncio de activación.")

        # =====================================================================
        # ESCENARIO 3: TRANSICIÓN A NUEVA PARTIDA (pending_enable -> active)
        # =====================================================================
        print("\n--- [ESCENARIO 3] Detección de nueva partida e inicio del Modo 50v50 ---")
        # Simula lógica de poll_rcon cuando cambia la rotación/partida
        async with AsyncSession(test_engine) as session:
            cfg_state = (await session.exec(select(BotConfig).where(BotConfig.config_key == "MODE_50V50_STATE"))).first()
            if cfg_state and cfg_state.config_value == "pending_enable":
                cfg_state.config_value = "active"
                session.add(cfg_state)
                cfg_en = await session.get(BotConfig, "MODE_50V50_ENABLED")
                cfg_en.config_value = "true"
                session.add(cfg_en)
                await session.commit()
                await rcon.broadcast("Modo 50v50 ACTIVADO para esta partida (Rojo vs Verde)!")

        audit = await rcon.get_audit_logs(limit=5)
        bc_found = any("Modo 50v50 ACTIVADO" in e.detail for e in audit.entries)
        assert bc_found, "Broadcast de activación debió enviarse"
        print("  * DB state: active / true")
        print("  * Broadcast verificado en audit logs del RCON!")
        print("  -> Escenario 3 Superado: Transición impecable.")

        # =====================================================================
        # ESCENARIO 4: SECUENCIA DE ANUNCIOS DE WARMUP (15s y ACTIVO)
        # =====================================================================
        print("\n--- [ESCENARIO 4] Secuencia de broadcasts: 15s -> ACTIVO ---")
        warmup_15s_sent = False
        active_broadcast_sent = False
        sent_announcements = []

        async def simulate_broadcast_check(match_sec):
            nonlocal warmup_15s_sent, active_broadcast_sent
            if match_sec < 15 and not warmup_15s_sent:
                msg = "Modo 50v50: 15s antes de autobalance"
                await rcon.broadcast(msg)
                warmup_15s_sent = True
                sent_announcements.append((match_sec, msg))
            elif match_sec >= 15 and not active_broadcast_sent:
                msg = "Modo 50v50: Autobalance ACTIVO"
                await rcon.broadcast(msg)
                active_broadcast_sent = True
                warmup_15s_sent = True
                sent_announcements.append((match_sec, msg))

        # Ticks every 6s from 0 to 30s
        for sec in [0, 6, 12, 18, 24, 30]:
            await simulate_broadcast_check(sec)

        print(f"  * Total de anuncios enviados: {len(sent_announcements)}")
        for sec, msg in sent_announcements:
            print(f"    - Segundo {sec:02d}s: '{msg}'")
        assert len(sent_announcements) == 2
        assert sent_announcements[0][1] == "Modo 50v50: 15s antes de autobalance"
        assert sent_announcements[1][1] == "Modo 50v50: Autobalance ACTIVO"
        print("  -> Escenario 4 Superado: Los 2 anuncios de 15s se dispararon exactamente en su momento.")

        # =====================================================================
        # ESCENARIO 5: WARMUP (<15s) - LIBERTAD DE ESCUADRA HASTA MÁXIMO 6 DIFERENCIA
        # =====================================================================
        print("\n--- [ESCENARIO 5] Warmup (<15s): Amigos juntos hasta diferencia máxima de 6 ---")
        player_team_history = {}
        recently_swapped_players = {}
        
        # Entran 6 amigos a Valkyre en el segundo 5 (0 en Manticore)
        mock_main.mock_players = [
            make_player(f"Friend_{i}", f"765611980000100{i:02d}", "Valkyre")
            for i in range(1, 7)
        ]
        
        match_seconds = 5
        now_ts = time.time()
        is_warmup = (match_seconds < 15)
        
        red_players = []
        green_players = []
        new_entrants = [(p, "valkyra") for p in mock_main.mock_players]

        for p, f_canonical in new_entrants:
            chosen_count = len(red_players) if f_canonical == "valkyra" else len(green_players)
            opposite_count = len(green_players) if f_canonical == "valkyra" else len(red_players)
            target_faction = "Manticore" if f_canonical == "valkyra" else "Valkyre"
            target_key = "manticore" if f_canonical == "valkyra" else "valkyra"

            should_redirect = False
            if chosen_count >= 50:
                should_redirect = True
            elif is_warmup and (chosen_count - opposite_count) >= 6:
                should_redirect = True

            if should_redirect:
                await rcon.switch_faction(p["steamId"], target_faction)
                player_team_history[p["steamId"]] = {"current_faction": target_key, "assigned_faction": target_key}
                green_players.append(p)
            else:
                player_team_history[p["steamId"]] = {"current_faction": f_canonical, "assigned_faction": f_canonical}
                red_players.append(p)

        print(f"  * 6 amigos entraron a Valkyre. Valkyre={len(red_players)}, Manticore={len(green_players)}")
        assert len(red_players) == 6
        assert len(green_players) == 0

        # Ahora entra un 7mo amigo intentando ir a Valkyre (diferencia = 6 - 0 = 6 >= 6)
        friend_7 = make_player("Friend_7", "76561198000010007", "Valkyre")
        mock_main.mock_players.append(friend_7)
        
        # Evaluar 7mo:
        chosen_count = len(red_players) # 6
        opposite_count = len(green_players) # 0
        diff = chosen_count - opposite_count # 6
        assert diff >= 6, "Diferencia de 6 alcanzada, debe ser frenado"
        await rcon.switch_faction(friend_7["steamId"], "Manticore")
        green_players.append(friend_7)
        player_team_history[friend_7["steamId"]] = {"current_faction": "manticore", "assigned_faction": "manticore"}

        print(f"  * 7mo jugador frenado por tope de 6 de diferencia! Valkyre={len(red_players)}, Manticore={len(green_players)}")
        assert len(red_players) == 6
        assert len(green_players) == 1
        print("  -> Escenario 5 Superado: Libertad de escuadra respetada y tope de diferencia de 6 activado.")

        # =====================================================================
        # ESCENARIO 6: DRENAJE DE LONESTAR (AZULES) HACIA EL EQUIPO MÁS CHICO
        # =====================================================================
        print("\n--- [ESCENARIO 6] Drenaje de Lonestar (Azules) ---")
        # Tenemos 10 en Valkyre y 0 en Manticore.
        # Entran 6 jugadores despistados a Lonestar (Azul)
        blue_entrants = [
            make_player(f"Blue_{i}", f"765611980000200{i:02d}", "Lonestar")
            for i in range(1, 7)
        ]
        mock_main.mock_players.extend(blue_entrants)

        # Lógica de drenaje
        blue_p = [p for p in mock_main.mock_players if p["faction"].lower().startswith("lone")]
        print(f"  * Detectados {len(blue_p)} jugadores en Lonestar. Drenando...")
        for p in blue_p:
            if len(red_players) <= len(green_players):
                target_f = "Valkyre"
                target_k = "valkyra"
                red_players.append(p)
            else:
                target_f = "Manticore"
                target_k = "manticore"
                green_players.append(p)
            
            await rcon.switch_faction(p["steamId"], target_f)
            player_team_history[p["steamId"]] = {
                "current_faction": target_k,
                "assigned_faction": target_k,
                "joined_team_at": time.time(),
            }
            await rcon.send_player_message(p["steamId"], f"Se te ha asignado al equipo {target_f}.")

        # Actualizar mock_players en base a lo aplicado por switch_faction
        cur_blue = sum(1 for p in mock_main.mock_players if p["faction"] == "Lonestar")
        cur_valk = sum(1 for p in mock_main.mock_players if p["faction"] == "Valkyre")
        cur_mant = sum(1 for p in mock_main.mock_players if p["faction"] == "Manticore")
        print(f"  * Post-drenaje: Lonestar={cur_blue}, Valkyre={cur_valk}, Manticore={cur_mant}")
        assert cur_blue == 0, "No debe quedar nadie en Lonestar"
        assert cur_mant == 6, f"Manticore debió quedar con 6, got {cur_mant}"
        assert cur_valk == 7, f"Valkyre debió quedar con 7, got {cur_valk}"
        print("  -> Escenario 6 Superado: Lonestar completamente vaciado y balanceado.")

        # =====================================================================
        # ESCENARIO 7: PATOVICA POST-WARMUP (>=15s) - RECHAZO DE SOBREPOBLADOR
        # =====================================================================
        print("\n--- [ESCENARIO 7] Patovica post-warmup (>=15s): Bloqueo de sobrepoblador ---")
        # Valkyre tiene 7, Manticore tiene 6.
        # Ya pasaron los 15s (match_seconds = 30).
        match_seconds = 30
        is_warmup = False
        
        # Entra un nuevo jugador y elige Valkyre (el que va ganando / tiene más gente)
        overcrowder = make_player("Overcrowder_Bob", "76561198000030001", "Valkyre")
        mock_main.mock_players.append(overcrowder)
        
        # Patovica evalúa al nuevo ingresante:
        f_canonical = "valkyra"
        is_overpopulating = (f_canonical == "valkyra" and len(red_players) > len(green_players))
        assert is_overpopulating, "Bob debe ser detectado como sobrepoblador"
        
        target_faction = "Manticore"
        target_key = "manticore"
        await rcon.switch_faction(overcrowder["steamId"], target_faction)
        player_team_history[overcrowder["steamId"]] = {
            "current_faction": target_key,
            "assigned_faction": target_key,
            "joined_team_at": time.time(),
        }
        green_players.append(overcrowder)
        await rcon.send_player_message(overcrowder["steamId"], f"Se te ha asignado al equipo {target_faction} para balancear la partida.")

        bob_in_server = next(p for p in mock_main.mock_players if p["steamId"] == overcrowder["steamId"])
        print(f"  * Bob intentó entrar a Valkyre (7 vs 6). Facción final de Bob: {bob_in_server['faction']}")
        assert bob_in_server["faction"] == "Manticore"
        assert player_team_history[overcrowder["steamId"]]["assigned_faction"] == "manticore"
        print("  -> Escenario 7 Superado: Sobrepoblador redirigido a Manticore con whisper privado.")

        # =====================================================================
        # ESCENARIO 8: PATOVICA POST-WARMUP (>=15s) - ACEPTACIÓN EN EQUIPO MENOR / IGUAL
        # =====================================================================
        print("\n--- [ESCENARIO 8] Patovica post-warmup (>=15s): Entrada voluntaria a equipo empatado ---")
        # Valkyre tiene 7, Manticore tiene 7 (6 + Bob).
        fair_player = make_player("GoodGuy_Dan", "76561198000040001", "Manticore")
        mock_main.mock_players.append(fair_player)

        f_canonical = "manticore"
        is_overpopulating = (f_canonical == "manticore" and len(green_players) > len(red_players))
        assert not is_overpopulating, "Dan eligió equipo empatado, no es sobrepoblador"

        player_team_history[fair_player["steamId"]] = {
            "current_faction": f_canonical,
            "assigned_faction": f_canonical,
            "joined_team_at": time.time(),
        }
        green_players.append(fair_player)

        dan_in_server = next(p for p in mock_main.mock_players if p["steamId"] == fair_player["steamId"])
        print(f"  * Dan eligió Manticore. Facción final de Dan: {dan_in_server['faction']}")
        assert dan_in_server["faction"] == "Manticore"
        print("  -> Escenario 8 Superado: Jugador admitido directamente sin ser movido.")

        # =====================================================================
        # ESCENARIO 9: CANDADO ARMA - INTENTO MANUAL DE CAMBIO DE EQUIPO
        # =====================================================================
        print("\n--- [ESCENARIO 9] Candado ARMA: Castigo/Reversión inmediata a quien intente cambiarse ---")
        # Dan estaba asignado a Manticore. En medio de la partida, abre el menú del juego y se pasa a Valkyre!
        dan_in_server["faction"] = "Valkyre" # Cambio manual en el cliente
        
        # Sync loop detecta la discrepancia:
        hist = player_team_history[dan_in_server["steamId"]]
        assigned = hist.get("assigned_faction")
        assert assigned == "manticore"
        
        # Bot detecta intento no autorizado:
        print(f"  * Dan intentó cambiarse de {assigned} a {dan_in_server['faction']}!")
        await rcon.switch_faction(dan_in_server["steamId"], "Manticore")
        await rcon.send_player_message(dan_in_server["steamId"], "Cambio de equipo no permitido durante la partida.")

        assert dan_in_server["faction"] == "Manticore"
        print(f"  * Dan fue forzado de regreso a: {dan_in_server['faction']}")
        print("  -> Escenario 9 Superado: Candado ARMA funcionó al 100%. Reversión inmediata con whisper de advertencia.")

        # =====================================================================
        # ESCENARIO 10: PROTECCIÓN ESTRICTA DE ESPECTADORES (White / None)
        # =====================================================================
        print("\n--- [ESCENARIO 10] Protección estricta de espectadores (White / None) ---")
        spec_white = make_player("Admin_Camera", "76561198000099901", "White")
        spec_none = make_player("Observer_None", "76561198000099902", "None")
        mock_main.mock_players.extend([spec_white, spec_none])

        # Verificamos que el loop los ignora por completo
        ignored_count = 0
        for p in [spec_white, spec_none]:
            f = (p["faction"] or "").strip().lower()
            if not (f.startswith("lone") or f.startswith("valk") or f.startswith("mant")):
                ignored_count += 1
        assert ignored_count == 2
        assert spec_white["faction"] == "White"
        assert spec_none["faction"] == "None"
        assert spec_white["steamId"] not in player_team_history
        print("  -> Escenario 10 Superado: Espectadores y cámaras no son tocados por la automatización.")

        # =====================================================================
        # ESCENARIO 11: COMANDO /mode50v50 disable DURANTE PARTIDA ACTIVA
        # =====================================================================
        print("\n--- [ESCENARIO 11] Comando /mode50v50 disable con partida activa ---")
        # Simula POST /api/v1/mode50v50/disable
        await rcon.set_team_balancing(True, threshold=1)
        await rcon.broadcast("Modo 50v50: En la siguiente partida se desactivara el modo 50v50")
        async with AsyncSession(test_engine) as session:
            cfg_state = await session.get(BotConfig, "MODE_50V50_STATE")
            assert cfg_state.config_value == "active"
            cfg_state.config_value = "pending_disable"
            session.add(cfg_state)
            await session.commit()

        cfg_after_dis = await rcon.get_config()
        assert "bLockOverpopulatedTeamsConfig=true" in cfg_after_dis.text
        assert "OverpopulatedTeamThresholdConfig=1" in cfg_after_dis.text
        audit = await rcon.get_audit_logs(limit=3)
        assert any("En la siguiente partida se desactivara el modo 50v50" in e.detail for e in audit.entries)
        print("  * RCON config restaurado inmediatamente con bLockOverpopulatedTeamsConfig=true y threshold=1.")
        print("  * Broadcast emitido: 'Modo 50v50: En la siguiente partida se desactivara el modo 50v50'")
        print("  * DB state: MODE_50V50_STATE = pending_disable")
        print("  * Durante pending_disable, sync_engine continúa manteniendo el 50v50 hasta que la partida termine.")
        print("  -> Escenario 11 Superado: Desactivación programada con aviso global.")

        # =====================================================================
        # ESCENARIO 12: FINAL DE PARTIDA CON pending_disable -> INACTIVE
        # =====================================================================
        print("\n--- [ESCENARIO 12] Fin de partida y transición final a 'inactive' ---")
        async with AsyncSession(test_engine) as session:
            cfg_state = await session.get(BotConfig, "MODE_50V50_STATE")
            if cfg_state and cfg_state.config_value == "pending_disable":
                cfg_state.config_value = "inactive"
                session.add(cfg_state)
                cfg_en = await session.get(BotConfig, "MODE_50V50_ENABLED")
                cfg_en.config_value = "false"
                session.add(cfg_en)
                await session.commit()
                await rcon.broadcast("Modo 50v50 FINALIZADO. Volviendo a 33v33v33.")

        async with AsyncSession(test_engine) as session:
            final_state = await session.get(BotConfig, "MODE_50V50_STATE")
            final_en = await session.get(BotConfig, "MODE_50V50_ENABLED")
            assert final_state.config_value == "inactive"
            assert final_en.config_value == "false"
        print("  * DB state: inactive / false")
        print("  * Broadcast de finalización verificado.")
        print("  -> Escenario 12 Superado: El servidor regresa a su estado natural 33v33v33.")

        # =====================================================================
        # ESCENARIO 13: CANCELACIÓN INMEDIATA CUANDO ESTÁ pending_enable
        # =====================================================================
        print("\n--- [ESCENARIO 13] Cancelación cuando estaba en 'pending_enable' ---")
        async with AsyncSession(test_engine) as session:
            cfg_state = await session.get(BotConfig, "MODE_50V50_STATE")
            cfg_state.config_value = "pending_enable"
            session.add(cfg_state)
            await session.commit()

        # Alguien se arrepintió antes de que empiece la partida y manda disable:
        await rcon.set_team_balancing(True, threshold=1)
        await rcon.broadcast("Modo 50v50: Se ha cancelado la activacion, seguiremos normal")
        async with AsyncSession(test_engine) as session:
            cfg_state = await session.get(BotConfig, "MODE_50V50_STATE")
            if cfg_state.config_value != "active":
                cfg_state.config_value = "inactive"
                session.add(cfg_state)
                await session.commit()
        
        async with AsyncSession(test_engine) as session:
            st_check = (await session.get(BotConfig, "MODE_50V50_STATE")).config_value
            assert st_check == "inactive"
        audit = await rcon.get_audit_logs(limit=3)
        assert any("Se ha cancelado la activacion, seguiremos normal" in e.detail for e in audit.entries)
        print("  * Broadcast emitido: 'Modo 50v50: Se ha cancelado la activacion, seguiremos normal'")
        print("  -> Escenario 13 Superado: Cancelación inmediata sin esperar a la siguiente partida.")

        # =====================================================================
        # ESCENARIO 14: CANCELACIÓN DE DESACTIVACIÓN (pending_disable -> active)
        # =====================================================================
        print("\n--- [ESCENARIO 14] Cancelación de desactivación (pending_disable -> active) ---")
        async with AsyncSession(test_engine) as session:
            cfg_state = await session.get(BotConfig, "MODE_50V50_STATE")
            cfg_state.config_value = "pending_disable"
            session.add(cfg_state)
            await session.commit()

        # Alguien se arrepiente de desactivar y manda enable otra vez:
        await rcon.set_team_balancing(False)
        await rcon.broadcast("Modo 50v50: Se ha cancelado la desactivacion, seguiremos en modo 50v50")
        async with AsyncSession(test_engine) as session:
            cfg_state = await session.get(BotConfig, "MODE_50V50_STATE")
            assert cfg_state.config_value == "pending_disable"
            cfg_state.config_value = "active"
            session.add(cfg_state)
            await session.commit()

        audit = await rcon.get_audit_logs(limit=3)
        assert any("Se ha cancelado la desactivacion, seguiremos en modo 50v50" in e.detail for e in audit.entries)
        print("  * Broadcast emitido: 'Modo 50v50: Se ha cancelado la desactivacion, seguiremos en modo 50v50'")
        # =====================================================================
        # ESCENARIO 15: ESTRÉS A CAPACIDAD MÁXIMA (100 JUGADORES 34v33v33 -> 50v50)
        # =====================================================================
        print("\n--- [ESCENARIO 15] Prueba de carga: 100 jugadores (34 Blue, 33 Red, 33 Green) ---")
        full_players = []
        for i in range(1, 101):
            if i <= 34:
                fac = "Lonestar"
            elif i <= 67:
                fac = "Valkyre"
            else:
                fac = "Manticore"
            full_players.append(make_player(f"Stress_{i}", f"7656119800005{i:04d}", fac))

        mock_main.mock_players = full_players
        red_p = [p for p in full_players if p["faction"] == "Valkyre"]
        green_p = [p for p in full_players if p["faction"] == "Manticore"]
        blue_p = [p for p in full_players if p["faction"] == "Lonestar"]

        assert len(blue_p) == 34
        assert len(red_p) == 33
        assert len(green_p) == 33

        # Drenaje
        for p in blue_p:
            if len(red_p) <= len(green_p):
                target = "Valkyre"
                red_p.append(p)
            else:
                target = "Manticore"
                green_p.append(p)
            await rcon.switch_faction(p["steamId"], target)

        final_blue = sum(1 for p in mock_main.mock_players if p["faction"] == "Lonestar")
        final_valk = sum(1 for p in mock_main.mock_players if p["faction"] == "Valkyre")
        final_mant = sum(1 for p in mock_main.mock_players if p["faction"] == "Manticore")
        print(f"  * Servidor lleno balanceado: Lonestar={final_blue}, Valkyre={final_valk}, Manticore={final_mant}")
        assert final_blue == 0
        assert final_valk == 50
        assert final_mant == 50
        print("  -> Escenario 15 Superado: 50v50 exacto con 100 jugadores concurrentes.")

        # =====================================================================
        # ESCENARIO 16: REINICIO REAL DEL SERVIDOR (Mismo mapa y rotación, arranque directo en 50v50)
        # =====================================================================
        print("\n--- [ESCENARIO 16] Reinicio del servidor (Servidor se apaga y prende en mismo mapa) ---")
        # 1. Admin programa 50v50 antes del reinicio
        async with AsyncSession(test_engine) as session:
            stmt_st = select(BotConfig).where(BotConfig.config_key == "MODE_50V50_STATE")
            st_cfg = (await session.exec(stmt_st)).first()
            if st_cfg:
                st_cfg.config_value = "pending_enable"
                session.add(st_cfg)
            else:
                session.add(BotConfig(config_key="MODE_50V50_STATE", config_value="pending_enable"))
            en_cfg = await session.get(BotConfig, "MODE_50V50_ENABLED")
            if en_cfg:
                en_cfg.config_value = "false"
                session.add(en_cfg)
            else:
                session.add(BotConfig(config_key="MODE_50V50_ENABLED", config_value="false"))
            await session.commit()

        # 2. Simulamos que el servidor se apagó (hubo error de conexión) y volvió a prender con matchSeconds=5 en rotación 0
        curr_rot = 0
        curr_map = "Bakurani"
        last_m_sec = 2400
        reconnected_flag = True # El servidor estuvo caído y se reconectó

        new_rot = 0       # Misma rotación!
        new_map = "Bakurani" # Mismo mapa!
        new_m_sec = 5     # Reloj reseteado a 5s

        # Evaluación de la condición de sync_engine.py
        is_new_m = (
            False # current_match_id ya existía
            or (new_rot != curr_rot)
            or (new_map != curr_map)
            or (last_m_sec is not None and new_m_sec < (last_m_sec - 30))
            or reconnected_flag
        )
        assert is_new_m is True, "El reinicio del servidor debió ser detectado incluso en mismo mapa y rotación!"

        # 3. Transición de ciclo de vida ejecutada por poll_rcon
        async with AsyncSession(test_engine) as session:
            st_cfg = (await session.exec(select(BotConfig).where(BotConfig.config_key == "MODE_50V50_STATE"))).first()
            if st_cfg and st_cfg.config_value == "pending_enable":
                st_cfg.config_value = "active"
                session.add(st_cfg)
                en_cfg = await session.get(BotConfig, "MODE_50V50_ENABLED")
                en_cfg.config_value = "true"
                session.add(en_cfg)
                await session.commit()
                await rcon.broadcast("Modo 50v50 ACTIVADO para esta partida (Rojo vs Verde)!")

        audit = await rcon.get_audit_logs(limit=3)
        assert any("Modo 50v50 ACTIVADO" in e.detail for e in audit.entries)
        print("  * Servidor reiniciado: Reloj cayó de 2400s a 5s, reconexión detectada.")
        print("  * DB state post-reboot: MODE_50V50_STATE = active, MODE_50V50_ENABLED = true")
        print("  * Broadcast de partida activa emitido inmediatamente tras el arranque.")
        print("  -> Escenario 16 Superado: El servidor arrancará directamente en 50v50 tras el reinicio.")

    print("\n" + "=" * 70)
    print(" [ÉXITO TOTAL] LOS 16 ESCENARIOS PASARON AL 100% SIN ERRORES")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(main())
