import crescent
import time
import asyncio
import hikari
from crescent.ext import tasks
from src.model import Model
import os
import datetime
import logging

plugin = crescent.Plugin[hikari.GatewayBot, Model]()
logger = logging.getLogger("wardogs.tasks")

# Tarea de monitoreo de partida
@plugin.include
@tasks.loop(seconds=10)
async def match_monitor():
    if not plugin.model.api:
        return
        
    try:
        status = await plugin.model.api.get_status()
        
        score_cap = status.scoreCap or 100
        current_tick = status.scoreTick.current if status.scoreTick and status.scoreTick.current is not None else 0
        
        # Verificar si se alcanzo el limite de puntos
        match_ended = current_tick >= score_cap
        
        current_map = status.map or "Unknown"
        now_index = status.rotation.nowIndex if status.rotation else 0
        match_identifier = f"{current_map}_{now_index}"
        
        logger.debug(f"[Match Monitor] Revisando estado: Mapa={current_map}, Tick={current_tick}/{score_cap}, Tiempo Restante={status.matchSeconds}s")
        
        # Si acaba de terminar y no lo hemos procesado
        if match_ended and plugin.model.active_match_id != f"{match_identifier}_ended":
            logger.info(f"[Match Monitor] 🏆 ¡PARTIDA TERMINADA en {current_map}! (ID: {match_identifier})")
            plugin.model.active_match_id = f"{match_identifier}_ended"
            
            # Obtener a los jugadores
            players_data = await plugin.model.api.get_players()
            players = players_data.players or []
            
            if players:
                # El mejor jugador
                players.sort(key=lambda x: x.kills or 0, reverse=True)
                mvp = players[0]
                mvp_name = mvp.name or "Unknown"
                mvp_steam = mvp.steamId or ""
                
                logger.info(f"[Match Monitor] 🏅 MVP Detectado: {mvp_name} ({mvp_steam}) con {mvp.kills} kills.")
                
                # Regalar 1 dia VIP
                if mvp_steam:
                    await plugin.model.api.add_membership(mvp_steam, "VIP_MVP_GIFT", 1)
                    logger.info(f"[Match Monitor] 🎁 Membresía VIP de 1 día otorgada a {mvp_name}.")
                    
                    # Anunciar en RCON
                    await plugin.model.api.broadcast(f"¡Partida terminada! MVP: {mvp_name}. ¡Ha ganado 1 día de VIP!")
                    
                    # Anunciar en Discord
                    channel_id_str = await plugin.model.api.get_bot_config("ANNOUNCEMENT_CHANNEL_ID")
                    if channel_id_str and plugin.app:
                        try:
                            await plugin.app.rest.create_message(
                                int(channel_id_str),
                                content=f"🏆 ¡La partida en **{current_map}** ha terminado!\nEl MVP fue **{mvp_name}** (`{mvp_steam}`). Se le ha otorgado 1 día de VIP gratis."
                            )
                            logger.info(f"[Match Monitor] 📢 Anuncio enviado a Discord (Canal: {channel_id_str}).")
                        except Exception as e:
                            logger.error(f"[Match Monitor] No se pudo enviar el mensaje a Discord: {e}")
                            
        elif not match_ended:
            if plugin.model.active_match_id != f"{match_identifier}_running":
                logger.info(f"[Match Monitor] ⚔️ Nueva partida en curso: {current_map} (ID: {match_identifier})")
            # Si el score baja (nueva partida)
            plugin.model.active_match_id = f"{match_identifier}_running"
            
        # Update Bot Presence
        if plugin.app and plugin.app.is_alive:
            current_players = status.players.current if status.players else 0
            max_players = status.players.max if status.players else 0
            presence_text = f"{current_map} | {current_players}/{max_players}"
            await plugin.app.update_presence(
                activity=hikari.Activity(
                    name=presence_text,
                    type=hikari.ActivityType.PLAYING
                )
            )
            
    except Exception as e:
        logger.error(f"[Match Monitor] Error en la automatización: {e}")

# Tarea de monitoreo de ingreso de VIPs
@plugin.include
@tasks.loop(seconds=10)
async def vip_monitor():
    if not plugin.model.api:
        return
        
    try:
        data = await plugin.model.api.get_players()
        players = data.players or []
        
        current_steam_ids = {p.steamId for p in players if p.steamId}
        
        # Detectar nuevos jugadores
        cached_ids = set(plugin.model.players_cache.keys())
        new_ids = current_steam_ids - cached_ids
        
        if not plugin.model.initial_scan_done:
            plugin.model.initial_scan_done = True
            logger.info(f"[VIP Monitor] 🚪 Escaneo inicial completado. {len(current_steam_ids)} jugadores en servidor. Omitiendo saludos.")
        elif len(new_ids) > 5:
            logger.info(f"[VIP Monitor] 🚪 Carga masiva detectada ({len(new_ids)} jugadores). Omitiendo mensajes de bienvenida.")
        else:
            if new_ids:
                logger.info(f"[VIP Monitor] 🚪 {len(new_ids)} jugador(es) nuevo(s) detectado(s). Analizando roles...")
            
            # Procesar nuevos jugadores
            for steam_id in new_ids:
                user_data = await plugin.model.api.get_player_by_steam(steam_id)
                if user_data:
                    welcome_message = user_data.get("custom_welcome_message")
                    active_role = user_data.get("active_role")
                    
                    # Verificar que todavia sea VIP o ADMIN
                    if welcome_message and active_role:
                        now = time.time()
                        last_seen = plugin.model.player_last_seen.get(steam_id, 0)
                        
                        # Fix: Don't re-announce if we saw them less than 5 minutes ago (handles map rotations / quick reconnects)
                        if now - last_seen < 300:
                            continue
                            
                        target_player = next((p for p in players if p.steamId == steam_id), None)
                        player_name = target_player.name if target_player else "Jugador"
                        
                        formatted_msg = f"El {active_role} {player_name} se conectó: \"{welcome_message}\""
                        logger.info(f"[VIP Monitor] ✨ ¡VIP ingresó! Enviando mensaje: '{formatted_msg}'")
                        
                        # Enviar broadcast
                        await plugin.model.api.broadcast(formatted_msg)
                        
                        # Fix: Delay between broadcasts to avoid RCON bursts that overwrite previous messages
                        await asyncio.sleep(4)
        
        # Detectar gastos (decremento de cash) y actualizar last_seen
        now = time.time()
        for p in players:
            sid = p.steamId
            plugin.model.player_last_seen[sid] = now
            
            current_cash = p.cash or 0
            if sid in plugin.model.players_cache:
                prev_cash = plugin.model.players_cache[sid]
                if current_cash < prev_cash:
                    spent = prev_cash - current_cash
                    logger.info(f"[Economy Monitor] 💸 El jugador {p.name} ({sid}) gastó ${spent}. Cash actual: ${current_cash}")
                    # TODO: Registrar 'spent' en stats_history
            plugin.model.players_cache[sid] = current_cash
            
        # Limpiar desconectados
        disconnected = cached_ids - current_steam_ids
        for sid in disconnected:
            if sid in plugin.model.players_cache:
                logger.debug(f"[VIP Monitor] 🔌 Jugador {sid} desconectado. Limpiando caché.")
                del plugin.model.players_cache[sid]
                
    except Exception as e:
        logger.error(f"[VIP Monitor] Error en la automatización: {e}")

# Tarea de sincronización de membresías y roles
@plugin.include
@tasks.loop(minutes=1)
async def membership_monitor():
    if not plugin.model.api or not plugin.app:
        return
        
    try:
        res = await plugin.model.api.sync_memberships()
        sync_data = res.get("sync_data", [])
        role_maps = res.get("role_maps", {})
        managed_special_roles = res.get("managed_special_roles", [])
        
        configs = await plugin.model.api.get_bot_configs()
        wl_str = configs.get("SYNC_WHITELIST", "")
        whitelist = set(wl_str.split(",")) if wl_str else set()
        
        all_managed_roles = set(role_maps.values()).union(set(managed_special_roles))
        
        if not all_managed_roles:
            return
            
        for user_data in sync_data:
            discord_id_str = user_data.get("discord_id")
            
            if not discord_id_str:
                continue
                
            if discord_id_str in whitelist:
                logger.info(f"[Sync] Usuario {discord_id_str} está en Whitelist, saltando sincronización.")
                continue
                
            active_memberships = user_data.get("active_memberships", [])
            special_roles = user_data.get("special_roles", [])
            
            discord_id = int(discord_id_str)
            
            roles_to_have = []
            for m_type in active_memberships:
                r_id = role_maps.get(m_type)
                if r_id:
                    roles_to_have.append(int(r_id))
                    
            for sr in special_roles:
                roles_to_have.append(int(sr))
                    
            for guild_id in plugin.app.cache.get_guilds_view():
                try:
                    member = plugin.app.cache.get_member(guild_id, discord_id)
                    if not member:
                        member = await plugin.app.rest.fetch_member(guild_id, discord_id)
                    
                    if member:
                        current_roles = set(member.role_ids)
                        
                        # Remove managed roles they shouldn't have
                        for r_id in all_managed_roles:
                            if r_id in current_roles and r_id not in roles_to_have:
                                await plugin.app.rest.remove_role_from_member(guild_id, discord_id, r_id)
                                logger.info(f"[Sync] Rol {r_id} removido de {discord_id} (Expiró/Revocado)")
                                
                        # Add roles they should have
                        for r_id in roles_to_have:
                            if r_id not in current_roles:
                                await plugin.app.rest.add_role_to_member(guild_id, discord_id, r_id)
                                logger.info(f"[Sync] Rol {r_id} añadido a {discord_id} (Sincronizado)")
                                
                except hikari.NotFoundError:
                    pass
                except Exception as e:
                    logger.error(f"[Sync] Error actualizando roles de {discord_id}: {e}")
                    
    except Exception as e:
        logger.error(f"[Sync] Error en la automatización: {e}")

@plugin.include
@tasks.loop(seconds=5)
async def hacker_monitor_task():
    if not plugin.model.api or not plugin.app or not getattr(plugin.model, "hacker_monitors", None):
        return

    monitors_to_remove = []
    
    try:
        status = await plugin.model.api.get_players()
        players = status.players or []
        
        for steam_id, monitor_data in list(plugin.model.hacker_monitors.items()):
            target_player = next((p for p in players if p.steamId == steam_id), None)
            
            if not target_player:
                embed = hikari.Embed(
                    title="🛑 Monitoreo Finalizado",
                    description=f"El jugador {monitor_data['player_name']} ha abandonado la partida.",
                    color=0x95a5a6
                )
                try:
                    await plugin.app.rest.edit_message(monitor_data['channel_id'], monitor_data['message_id'], embed=embed, components=[])
                except Exception:
                    pass
                monitors_to_remove.append(steam_id)
                continue
                
            current_kills = target_player.kills or 0
            start_kills = monitor_data["start_kills"]
            start_time = monitor_data["start_time"]
            
            elapsed_seconds = time.time() - start_time
            elapsed_minutes = elapsed_seconds / 60.0
            
            # Avoid division by very small numbers initially
            if elapsed_minutes < 0.05:
                elapsed_minutes = 0.05
                
            kpm = (current_kills - start_kills) / elapsed_minutes
            
            # Update last kills for potential reference
            monitor_data["last_kills"] = current_kills
            
            color = 0x3498db # Blue by default
            alert_msg = "Calculando métricas en tiempo real..."
            
            # If KPM > 1.0 and we've measured for at least 1 minute (60s)
            if elapsed_seconds > 60:
                if kpm > 1.0:
                    color = 0xe74c3c # Red
                    alert_msg = "⚠️ **¡ALERTA!** KPM anormalmente alto (>1.0). Posible hack o vehículo pesado."
                else:
                    color = 0x2ecc71 # Green
                    alert_msg = "Monitoreo en curso. Tasa de KPM dentro de rangos normales."
                
            embed = hikari.Embed(
                title=f"🕵️ Monitoreando a: {target_player.name}",
                description=alert_msg,
                color=color
            )
            embed.add_field(name="Kills (Inicial -> Actual)", value=f"{start_kills} -> **{current_kills}**", inline=True)
            embed.add_field(name="Tiempo (Minutos)", value=f"{elapsed_minutes:.2f}m", inline=True)
            embed.add_field(name="KPM (Kills/Min)", value=f"**{kpm:.2f}**", inline=True)
            
            try:
                await plugin.app.rest.edit_message(
                    monitor_data['channel_id'], 
                    monitor_data['message_id'], 
                    embed=embed
                )
            except hikari.NotFoundError:
                monitors_to_remove.append(steam_id) # Message was deleted
            except Exception as e:
                logger.error(f"[Hacker Monitor] Error updating message: {e}")
                
    except Exception as e:
        logger.error(f"[Hacker Monitor] Error in loop: {e}")
        
    for sid in monitors_to_remove:
        if sid in plugin.model.hacker_monitors:
            del plugin.model.hacker_monitors[sid]

@plugin.include
@tasks.loop(seconds=30)
async def match_announcer_task():
    if not plugin.model.api or not plugin.app:
        return
        
    try:
        # Get configured channel
        configs = await plugin.model.api.get_bot_configs()
        channel_id_str = configs.get("MATCH_ANNOUNCE_CHANNEL_ID")
        if not channel_id_str:
            return
            
        channel_id = int(channel_id_str)
        
        # Get latest match
        match = await plugin.model.api.get_latest_match()
        if not match or not match.get("end_time"):
            return
            
        # Check if already announced
        last_announced = configs.get("LAST_ANNOUNCED_MATCH_ID")
        if last_announced == match["id"]:
            return
            
        # We have a new finished match to announce!
        
        # Find winning team
        winning_team = next((ts for ts in match.get("team_stats", []) if ts["team_id"] == match.get("winning_team_id")), None)
        winning_team_name = winning_team["team_name"] if winning_team else "Empate/Desconocido"
        winning_score = winning_team["score"] if winning_team else 0
        
        # Find MVP (most kills)
        players = match.get("player_stats", [])
        mvp = max(players, key=lambda x: x.get("kills", 0), default=None) if players else None
        
        # Find Top Earner
        top_earner = max(players, key=lambda x: x.get("cash_earned", 0), default=None) if players else None
        
        # Get Steam names for MVP and Earner
        steam_ids_to_fetch = []
        if mvp: steam_ids_to_fetch.append(mvp["steam_id"])
        if top_earner: steam_ids_to_fetch.append(top_earner["steam_id"])
        
        steam_names = {}
        if steam_ids_to_fetch:
            steam_profiles = await plugin.model.api.get_steam_players_batch(steam_ids_to_fetch)
            for sid, profile in steam_profiles.items():
                if profile and "personaname" in profile:
                    steam_names[sid] = profile["personaname"]
                    
        mvp_name = steam_names.get(mvp["steam_id"], "Desconocido") if mvp else "N/A"
        top_earner_name = steam_names.get(top_earner["steam_id"], "Desconocido") if top_earner else "N/A"
        
        # Build Embed
        embed = hikari.Embed(
            title="🏁 ¡Partida Finalizada!",
            description=f"La batalla en **{match.get('map', 'Desconocido')}** ha terminado.",
            color=0xf1c40f # Gold
        )
        
        embed.add_field(name="🏆 Ganador", value=f"**{winning_team_name}** con {winning_score} puntos", inline=False)
        
        if mvp:
            embed.add_field(name="🥇 MVP de la Partida", value=f"**{mvp_name}** ({mvp.get('kills', 0)} Kills / {mvp.get('deaths', 0)} Deaths)", inline=True)
            
        if top_earner:
            embed.add_field(name="💰 Mayor Recaudación", value=f"**{top_earner_name}** (${top_earner.get('cash_earned', 0)})", inline=True)
            
        embed.set_footer(text=f"Match ID: {match['id'][:8]}")
        
        # Send
        await plugin.app.rest.create_message(channel_id, embed=embed)
        
        # Mark as announced
        await plugin.model.api.set_bot_config("LAST_ANNOUNCED_MATCH_ID", match["id"])
        logger.info(f"[Match Announcer] Anunciada partida {match['id']}")
        
    except Exception as e:
        logger.error(f"[Match Announcer] Error: {e}")
