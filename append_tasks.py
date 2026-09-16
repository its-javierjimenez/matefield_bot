import hikari
import datetime

code = '''
@plugin.include
@tasks.loop(seconds=15)
async def live_status_monitor():
    if not plugin.model.api:
        return
        
    try:
        channel_id_str = await plugin.model.api.get_bot_config("live_status_channel_id")
        message_id_str = await plugin.model.api.get_bot_config("live_status_message_id")
        
        if not channel_id_str or not message_id_str:
            return
            
        channel_id = int(channel_id_str)
        message_id = int(message_id_str)
        
        status = await plugin.model.api.get_status()
        players_data = await plugin.model.api.get_players()
        
        # Build Embed 1: Status
        server_name = status.serverName or "Desconocido"
        server_id = getattr(status, "serverId", "Desconocido")
        map_name = status.map or "Desconocido"
        lighting = status.lighting or "Desconocido"
        score_cap = status.scoreCap or 100
        
        players_current = status.players.current if status.players else 0
        players_max = status.players.max if status.players else 100
        
        embed_status = hikari.Embed(
            title="Estado del servidor - 🟢 ONLINE",
            color=0x1DD65C
        )
        embed_status.description = f"📛 **Nombre:** {server_name}\\n\\n🔗 **ID para unirse:** {server_id}"
        
        embed_status.add_field(name="🗺️ Partida", value=f"{map_name} - {lighting}", inline=False)
        embed_status.add_field(name="👥 Jugadores", value=f"{players_current}/{players_max}", inline=True)
        
        # Calculate duration
        duration_str = "Desconocido"
        if status.matchSeconds is not None:
            m, s = divmod(status.matchSeconds, 60)
            h, m = divmod(m, 60)
            duration_str = f"{h:02d}:{m:02d}:{s:02d}"
            
        embed_status.add_field(name="⏱️ Duración del match", value=duration_str, inline=True)
        
        next_map = "Desconocido"
        if status.experiences and status.rotation and status.rotation.nextIndex is not None:
            if status.rotation.nextIndex < len(status.experiences):
                next_map = status.experiences[status.rotation.nextIndex]
            
        embed_status.add_field(name="⏭️ Próximo mapa", value=next_map, inline=False)
        embed_status.set_footer(text=f"Actualizado • hoy a las {datetime.datetime.now().strftime('%H:%M')}")
        
        # Build Embed 2: Scoreboard
        embed_score = hikari.Embed(color=0x2B2D31) # Dark color
        
        factions = {"Lonestar": [], "Valkyra": [], "Manticore": []}
        if players_data and players_data.players:
            for p in players_data.players:
                if p.faction in factions:
                    factions[p.faction].append(p)
                    
        # Add faction scores if available
        scores = {}
        if status.factionScores:
            for f in status.factionScores:
                scores[f.name] = f.score
                
        for fname in ["Lonestar", "Valkyra", "Manticore"]:
            score = scores.get(fname, 0)
            
            p_list = sorted(factions[fname], key=lambda x: x.kills or 0, reverse=True)
            p_lines = []
            for p in p_list[:8]: # Show top 8 per faction
                name = (p.name[:10] + "..") if p.name and len(p.name) > 12 else (p.name or "Unknown")
                kills = p.kills or 0
                deaths = p.deaths or 0
                p_lines.append(f"{name:<12} {kills}/{deaths}")
            
            if len(p_list) > 8:
                p_lines.append(f"+{len(p_list)-8} más...")
                
            p_text = "`\\n" + "\\n".join(p_lines) + "\\n`" if p_lines else "`\\nVacío\\n`"
            embed_score.add_field(name=f"{fname} - {score}/{score_cap}", value=p_text, inline=True)
            
        # Build Embed 3: Banner
        embed_banner = hikari.Embed(color=0x2B2D31)
        # Using a default wardogs banner placeholder or the one from the image
        embed_banner.set_image("https://i.imgur.com/1G8O3v8.jpeg") # Fallback dummy image
        
        await plugin.app.rest.edit_message(channel_id, message_id, content="", embeds=[embed_status, embed_score, embed_banner])
        
    except hikari.errors.NotFoundError:
        logger.warning("[Live Status] Mensaje no encontrado. Borrando config.")
        await plugin.model.api.delete_bot_config("live_status_message_id")
    except Exception as e:
        logger.error(f"[Live Status] Error: {e}")
'''
with open('d:/proyectos_dev/server_rcon_automation/apps/discord_bot/src/plugins/tasks.py', 'a', encoding='utf-8') as f:
    f.write(code)
print("Done!")
