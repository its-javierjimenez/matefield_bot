import asyncio
import re

import crescent
import hikari
import time
import csv
import io
import logging

logger = logging.getLogger("wardogs.admin")

from src.hooks import admin_only
from src.model import Model

plugin = crescent.Plugin[hikari.GatewayBot, Model]()
from src.groups import reserved_group, server_group, quota_group, hacker_group, ban_group

# Grupo Reserved Slots

@plugin.include
@reserved_group.child
@crescent.command(name="list", description="Muestra la lista de Steam IDs en slots reservados")
class ReservedSlotsList:
    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer()
        try:
            data = await plugin.model.api.get_reserved_slots()
            slots = data.reservedSlots or []
            
            if not slots:
                await ctx.respond("No hay slots reservados configurados.")
                return
                
            steam_profiles = await plugin.model.api.get_steam_players_batch(slots)
            
            # 1. Optimización: Fetch DB players concurrentemente
            db_players_list = await asyncio.gather(*[plugin.model.api.get_player_by_steam(s) for s in slots])
            db_players = dict(zip(slots, db_players_list))
            
            async def resolve_discord_username(db_player_info):
                if not db_player_info or not db_player_info.get("discord_id"):
                    return "Desconocido"
                discord_id = int(db_player_info.get("discord_id"))
                
                # Check cache primero (0 costo)
                cached_user = plugin.app.cache.get_user(discord_id)
                if cached_user:
                    return cached_user.username
                    
                # Si no, buscar en la API
                try:
                    user = await ctx.app.rest.fetch_user(discord_id)
                    return user.username
                except:
                    return f"ID: {discord_id}"
            
            # 2. Optimización: Fetch Discord usernames concurrentemente (reduciendo a 1-2 segundos)
            discord_usernames = await asyncio.gather(*[resolve_discord_username(db_players.get(s)) for s in slots])
            discord_usernames_dict = dict(zip(slots, discord_usernames))
            
            lines = []
            for s in slots:
                steam_name = steam_profiles.get(s, {}).get("personaname", "Desconocido")
                discord_username = discord_usernames_dict.get(s, "Desconocido")
                lines.append(f"- `{s}` | Steam: **{steam_name}** | Discord: **{discord_username}**")
                
            msg = "**Jugadores en Slots Reservados:**\n"
            current_msg = msg
            for line in lines:
                if len(current_msg) + len(line) + 1 > 1900:
                    await ctx.respond(current_msg)
                    current_msg = ""
                current_msg += line + "\n"
            
            if current_msg:
                await ctx.respond(current_msg)
        except Exception as e:
            await ctx.respond(f"Error al consultar RCON o DB: {e}")

@plugin.include
@reserved_group.child
@crescent.command(name="add", description="Agrega un Steam ID a la lista de slots reservados")
class ReservedSlotsAdd:
    steam_id = crescent.option(str, "Steam ID a agregar")
    
    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer()
        try:
            await plugin.model.api.add_reserved_slot(self.steam_id)
            await ctx.respond(f"✅ Steam ID `{self.steam_id}` agregado a slots reservados.")
        except Exception as e:
            await ctx.respond(f"❌ Error al consultar RCON: {e}")

@plugin.include
@reserved_group.child
@crescent.command(name="remove", description="Remueve un Steam ID de la lista de slots reservados")
class ReservedSlotsRemove:
    steam_id = crescent.option(str, "Steam ID a remover")
    
    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer()
        try:
            await plugin.model.api.remove_reserved_slot(self.steam_id)
            await ctx.respond(f"✅ Steam ID `{self.steam_id}` removido de slots reservados.")
        except Exception as e:
            await ctx.respond(f"❌ Error al consultar RCON: {e}")

@plugin.include
@reserved_group.child
@crescent.command(name="sync_status", description="Muestra el estado de sincronización entre BD y RCON")
class ReservedSlotsSyncStatus:
    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer()
        try:
            status = await plugin.model.api.get_rcon_sync_status()
            
            synced = status.get("synced", [])
            pending_add = status.get("pending_add", [])
            pending_remove = status.get("pending_remove", [])
            
            embed = hikari.Embed(title="📊 Estado de Sincronización RCON", color=0x3498DB)
            
            synced_str = f"**{len(synced)} usuarios**" if len(synced) > 10 else ", ".join(f"`{s}`" for s in synced) or "Ninguno"
            pending_add_str = f"**{len(pending_add)} usuarios**" if len(pending_add) > 10 else ", ".join(f"`{s}`" for s in pending_add) or "Ninguno"
            pending_remove_str = f"**{len(pending_remove)} usuarios**" if len(pending_remove) > 10 else ", ".join(f"`{s}`" for s in pending_remove) or "Ninguno"
            
            embed.add_field(name="🟢 Sincronizados (OK)", value=synced_str, inline=False)
            embed.add_field(name="🟡 Pendientes por Añadir (Faltan en RCON)", value=pending_add_str, inline=False)
            embed.add_field(name="🔴 Pendientes por Remover (Sobran en RCON)", value=pending_remove_str, inline=False)
            
            embed.set_footer(text="Nota: La escritura a RCON está temporalmente pausada.")
            await ctx.respond(embed=embed)
        except Exception as e:
            await ctx.respond(f"❌ Error al consultar el estado de sincronización: {e}")



# Grupo Server

@plugin.include
@server_group.child
@server_group.child
@crescent.command(name="announce", description="Envía un anuncio al servidor RCON")
class ServerAnnounce:
    message = crescent.option(str, "Mensaje a enviar")
    
    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer()
        try:
            await plugin.model.api.broadcast(self.message)
            await ctx.respond(f"✅ Anuncio enviado:\n> {self.message}")
        except Exception as e:
            await ctx.respond(f"❌ Error al consultar RCON: {e}")

@plugin.include
@crescent.hook(admin_only)

@quota_group.child
@crescent.command(name="list", description="Revisar la ocupación de cupos de las membresías")
class CheckQuotas:
    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer()
        try:
            res = await plugin.model.api.get_quotas()
            quotas = res.get("quotas", [])
            
            if not quotas:
                await ctx.respond("ℹ️ No hay configuración de cupos. Todas las membresías son infinitas por defecto.")
                return
                
            embed = hikari.Embed(title="📊 Estado de Cupos VIP", color=0x3498db)
            for q in quotas:
                m_type = q.get("membership_type")
                current = q.get("current_usage", 0)
                max_q = q.get("max_quota")
                
                limit_str = str(max_q) if max_q is not None else "Infinito"
                status = "🟢 Disponible"
                if max_q is not None and current >= max_q:
                    status = "🔴 LLENO"
                    
                embed.add_field(name=f"Tipo: {m_type}", value=f"Ocupación: {current} / {limit_str}\nEstado: {status}", inline=False)
                
            await ctx.respond(embed=embed)
        except Exception as e:
            await ctx.respond(f"❌ Error al consultar cupos: {e}")

@plugin.include
@crescent.hook(admin_only)
@quota_group.child
@crescent.command(name="set", description="Configurar el límite de un tipo de membresía")
class SetQuota:
    membership_type = crescent.option(str, "El tipo exacto de membresía (ej. NITRO, VIP, FUNDADOR)")
    max_quota = crescent.option(int, "Límite máximo (Pon 0 o déjalo vacío para infinito)", default=0)
    
    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer()
        try:
            limit = self.max_quota if self.max_quota > 0 else None
            await plugin.model.api.update_quota(self.membership_type.upper(), limit)
            
            limit_str = str(limit) if limit is not None else "Infinito"
            await ctx.respond(f"✅ Cupo para `{self.membership_type.upper()}` configurado a **{limit_str}**.")
        except Exception as e:
            await ctx.respond(f"❌ Error al configurar cupo: {e}")

@plugin.include
@server_group.child

@server_group.child
@crescent.command(name="set_max_reserved", description="Modifica el límite máximo de slots reservados (ServerSettings.ini)")
class ServerSetMaxReserved:
    cantidad = crescent.option(int, "Cantidad máxima de slots reservados (0-128)")
    
    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer()
        try:
            # Primero obtenemos la configuración actual
            data = await plugin.model.api.get_config()
            
            revision = data.revision
            text = data.text or ""
                
            if not revision:
                await ctx.respond("❌ No se pudo obtener la revisión actual del archivo.")
                return

            # Reemplazar la linea MaxReservedSlots=... usando regex
            new_text = re.sub(
                r"(?im)^MaxReservedSlots=\d+",
                f"MaxReservedSlots={self.cantidad}",
                text
            )
            
            # Si no existia la clave, la podemos aniadir bajo la seccion correspondiente
            if "MaxReservedSlots=" not in new_text:
                new_text = new_text.replace(
                    "[/Script/WDGame.WDGameSession]",
                    f"[/Script/WDGame.WDGameSession]\nMaxReservedSlots={self.cantidad}"
                )
                
            # Hacer PUT
            await plugin.model.api.update_config(revision, new_text)
            await ctx.respond(f"✅ Límite de slots reservados actualizado a `{self.cantidad}`.")
        except Exception as e:
            await ctx.respond(f"❌ Error al actualizar configuración RCON: {e}")

@plugin.include
@crescent.hook(admin_only)

@hacker_group.child
@crescent.command(name="monitor", description="Monitorea a un jugador para detectar hacks usando KPM")
class MonitorHacker:
    steam_id = crescent.option(str, "Steam ID del jugador a monitorear")

    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer()
        
        # Check if already monitored
        if self.steam_id in plugin.model.hacker_monitors:
            await ctx.respond(f"El SteamID {self.steam_id} ya está siendo monitoreado.")
            return
            
        # Verify player is in the match and get their initial kills
        try:
            status = await plugin.model.api.get_players()
            players = status.players or []
            
            target_player = next((p for p in players if p.steamId == self.steam_id), None)
            
            if not target_player:
                await ctx.respond(f"❌ El jugador con SteamID {self.steam_id} no está en la partida.")
                return
                
            start_kills = target_player.kills or 0
            
            # Create interactive button
            components = [
                plugin.app.rest.build_message_action_row()
                .add_interactive_button(hikari.ButtonStyle.DANGER, f"stop_monitor_{self.steam_id}", label="🛑 Detener Monitoreo")
            ]
            
            embed = hikari.Embed(
                title=f"🕵️ Monitoreando a: {target_player.name}",
                description="Iniciando monitoreo de KPM (Kills per Minute)...",
                color=0x3498db
            )
            
            msg = await ctx.respond(embed=embed, components=components, ensure_message=True)
            message = msg
            
            if not message:
                await ctx.respond("❌ Error: No se pudo obtener el mensaje.")
                return
                
            plugin.model.hacker_monitors[self.steam_id] = {
                "message_id": message.id,
                "channel_id": message.channel_id,
                "start_time": time.time(),
                "start_kills": start_kills,
                "last_kills": start_kills,
                "player_name": target_player.name
            }
            
        except Exception as e:
            await ctx.respond(f"❌ Error al iniciar monitoreo: {e}")

@plugin.include
@crescent.event
async def on_button_click(event: hikari.InteractionCreateEvent) -> None:
    if not isinstance(event.interaction, hikari.ComponentInteraction):
        return

    if event.interaction.custom_id.startswith("stop_monitor_"):
        steam_id = event.interaction.custom_id.replace("stop_monitor_", "")
        
        if steam_id in plugin.model.hacker_monitors:
            del plugin.model.hacker_monitors[steam_id]
            
            embed = hikari.Embed(
                title="🛑 Monitoreo Detenido",
                description=f"El monitoreo para el SteamID {steam_id} ha sido detenido manualmente.",
                color=0x95a5a6
            )
            
            await event.interaction.create_initial_response(
                hikari.ResponseType.MESSAGE_UPDATE,
                embed=embed,
                components=[]
            )
        else:
            await event.interaction.create_initial_response(
                hikari.ResponseType.MESSAGE_CREATE,
                "Este monitoreo ya no está activo.",
                flags=hikari.MessageFlag.EPHEMERAL
            )

@plugin.include
@crescent.hook(admin_only)

@plugin.include
@crescent.hook(admin_only)
@ban_group.child

@ban_group.child
@crescent.command(name="add", description="Banea a un jugador por Steam ID o @usuario y sincroniza con RCON")
class BanPlayer:
    steam_id: str | None = crescent.option(str, "Steam ID a banear (opcional si especificas usuario)", default=None)
    usuario: hikari.User | None = crescent.option(hikari.User, "Usuario de Discord a banear (opcional si especificas steam_id)", default=None)
    reason: str = crescent.option(str, "Razón del ban", default="No especificado")
    dias: int = crescent.option(int, "Duración en días (0 = permanente)", default=0)
    
    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer()
        if not self.steam_id and not self.usuario:
            await ctx.respond("❌ Debes especificar al menos un `steam_id` o un `usuario` de Discord.")
            return

        target_steam = self.steam_id
        target_discord_id = self.usuario.id if self.usuario else None

        try:
            if self.usuario and not target_steam:
                db_player = await plugin.model.api.get_player_by_discord(str(self.usuario.id))
                if not db_player or not db_player.get("steam_id"):
                    await ctx.respond(f"❌ El usuario {self.usuario.mention} no tiene una cuenta vinculada con Steam en la base de datos.")
                    return
                target_steam = db_player["steam_id"]

            if target_steam and not target_discord_id:
                db_player = await plugin.model.api.get_player_by_steam(str(target_steam))
                if db_player and db_player.get("discord_id"):
                    target_discord_id = int(db_player["discord_id"])

            # 1. Ban en DB y RCON
            await plugin.model.api.ban_player(str(target_steam), str(self.reason), self.dias)
            
            dur_str = "permanentemente" if self.dias == 0 else f"por {self.dias} días"
            target_mention = f"<@{target_discord_id}>" if target_discord_id else f"`{target_steam}`"
            msg = f"✅ Jugador {target_mention} (`{target_steam}`) baneado {dur_str}. Razón: {self.reason}"
            
            # 2. Asignar rol de ban en Discord si está vinculado y mapeado (sin remover rol de link)
            if target_discord_id and ctx.guild_id:
                try:
                    ban_role_id = await plugin.model.api.get_bot_config("BAN_ROLE_DEFAULT")
                    if not ban_role_id or not ban_role_id.isdigit():
                        ban_role_id = await plugin.model.api.get_bot_config(f"BAN_ROLE_{self.dias}")
                    
                    if ban_role_id and ban_role_id.isdigit():
                        member = plugin.app.cache.get_member(ctx.guild_id, target_discord_id) or await ctx.app.rest.fetch_member(ctx.guild_id, target_discord_id)
                        if member and int(ban_role_id) not in member.role_ids:
                            await member.add_role(int(ban_role_id), reason=f"Baneado {dur_str}: {self.reason}")
                            msg += f"\n🔒 Rol de ban <@&{ban_role_id}> asignado a <@{target_discord_id}> (rol de link conservado)."
                except Exception as ex:
                    msg += f"\n⚠️ No se pudo asignar el rol de ban en Discord: {ex}"
            
            await ctx.respond(msg)
        except Exception as e:
            await ctx.respond(f"❌ Error al banear: {e}")

@plugin.include
@crescent.hook(admin_only)
@ban_group.child
@crescent.command(name="remove", description="Desbanea a un jugador por Steam ID o @usuario y sincroniza con RCON")
class UnbanPlayer:
    steam_id: str | None = crescent.option(str, "Steam ID a desbanear (opcional si especificas usuario)", default=None)
    usuario: hikari.User | None = crescent.option(hikari.User, "Usuario de Discord a desbanear (opcional si especificas steam_id)", default=None)
    
    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer()
        if not self.steam_id and not self.usuario:
            await ctx.respond("❌ Debes especificar un `steam_id` o un `usuario` de Discord a desbanear.")
            return

        target_steam = self.steam_id
        target_discord_id = self.usuario.id if self.usuario else None

        try:
            if self.usuario and not target_steam:
                db_player = await plugin.model.api.get_player_by_discord(str(self.usuario.id))
                if not db_player or not db_player.get("steam_id"):
                    await ctx.respond(f"❌ El usuario {self.usuario.mention} no tiene una cuenta vinculada en la base de datos.")
                    return
                target_steam = db_player["steam_id"]

            if target_steam and not target_discord_id:
                db_player = await plugin.model.api.get_player_by_steam(str(target_steam))
                if db_player and db_player.get("discord_id"):
                    target_discord_id = int(db_player["discord_id"])

            await plugin.model.api.unban_player(str(target_steam))
            target_mention = f"<@{target_discord_id}>" if target_discord_id else f"`{target_steam}`"
            msg = f"✅ Jugador {target_mention} (`{target_steam}`) desbaneado y sincronizado con RCON."
            
            # Quitar roles de ban en Discord (sin tocar el rol de link)
            if target_discord_id and ctx.guild_id:
                try:
                    configs = await plugin.model.api.get_bot_configs()
                    ban_roles = [int(v) for k, v in configs.items() if (k == "BAN_ROLE_DEFAULT" or k.startswith("BAN_ROLE_")) and v.isdigit()]
                    
                    if ban_roles:
                        member = plugin.app.cache.get_member(ctx.guild_id, target_discord_id) or await ctx.app.rest.fetch_member(ctx.guild_id, target_discord_id)
                        if member:
                            removed = 0
                            for role_id in set(ban_roles):
                                if role_id in member.role_ids:
                                    await member.remove_role(role_id, reason="Desbaneado")
                                    removed += 1
                            if removed > 0:
                                msg += f"\n🔓 Se removió el rol de ban a <@{target_discord_id}> (rol de link conservado)."
                except Exception as ex:
                    msg += f"\n⚠️ No se pudieron quitar los roles de ban en Discord: {ex}"
            
            await ctx.respond(msg)
        except Exception as e:
            await ctx.respond(f"❌ Error al desbanear: {e}")

@plugin.include
@ban_group.child
@crescent.command(name="list", description="Muestra la lista de baneos, con opción de filtrar")
class BanList:
    steam_id = crescent.option(str, "Filtrar por Steam ID", default=None)
    usuario = crescent.option(hikari.User, "Filtrar por usuario de Discord", default=None)

    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer()
        try:
            target_steam = self.steam_id
            
            if self.usuario:
                db_player = await plugin.model.api.get_player_by_discord(str(self.usuario.id))
                if not db_player:
                    await ctx.respond(f"El usuario {self.usuario.mention} no tiene una cuenta vinculada.")
                    return
                target_steam = db_player.get("steam_id")
                
            data = await plugin.model.api.get_db_bans(str(target_steam) if target_steam else None)
            bans = data.bans if data else []
            
            if not bans:
                msg = "No hay baneos registrados."
                if target_steam:
                    msg = f"El Steam ID `{target_steam}` no tiene baneos activos."
                await ctx.respond(msg)
                return
                
            slots = [b.steam_id for b in bans]
            steam_profiles = await plugin.model.api.get_steam_players_batch(slots)
            
            # 1. Fetch DB players concurrentemente
            db_players_list = await asyncio.gather(*[plugin.model.api.get_player_by_steam(s) for s in slots])
            db_players = dict(zip(slots, db_players_list))
            
            async def resolve_discord_username(db_player_info):
                if not db_player_info or not db_player_info.get("discord_id"):
                    return "Desconocido"
                discord_id = int(db_player_info.get("discord_id"))
                cached_user = plugin.app.cache.get_user(discord_id)
                if cached_user:
                    return cached_user.username
                try:
                    user = await ctx.app.rest.fetch_user(discord_id)
                    return user.username
                except:
                    return f"ID: {discord_id}"
            
            # 2. Fetch Discord usernames concurrentemente
            discord_usernames = await asyncio.gather(*[resolve_discord_username(db_players.get(s)) for s in slots])
            discord_usernames_dict = dict(zip(slots, discord_usernames))
            
            lines = []
            for b in bans:
                steam_name = steam_profiles.get(b.steam_id, {}).get("personaname", "Desconocido")
                discord_username = discord_usernames_dict.get(b.steam_id, "Desconocido")
                lines.append(f"- `{b.steam_id}` | Steam: **{steam_name}** | Discord: **{discord_username}** | Razón: _{b.reason}_")
                
            msg = f"**Jugadores Baneados ({len(bans)}):**\n"
            current_msg = msg
            for line in lines:
                if len(current_msg) + len(line) + 1 > 1900:
                    await ctx.respond(current_msg)
                    current_msg = ""
                current_msg += line + "\n"
            
            if current_msg:
                await ctx.respond(current_msg)
        except Exception as e:
            await ctx.respond(f"Error al consultar la base de datos: {e}")
