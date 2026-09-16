import re

import crescent
import hikari
import csv
import io
import logging

logger = logging.getLogger("wardogs.admin")

from src.hooks import admin_only
from src.model import Model

plugin = crescent.Plugin[hikari.GatewayBot, Model]()

# Grupo Reserved Slots
reserved_group = crescent.Group("reserved_slots", description="Administración de slots reservados", hooks=[admin_only])

@plugin.include
@reserved_group.child
@crescent.command(name="list", description="Muestra la lista de Steam IDs en slots reservados")
class ReservedSlotsList:
    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer(ephemeral=True)
        try:
            data = await plugin.model.api.get_reserved_slots()
            slots = data.reservedSlots or []
            
            if not slots:
                await ctx.respond("No hay slots reservados configurados.")
                return
                
            steam_profiles = await plugin.model.api.get_steam_players_batch(slots)
            
            lines = []
            for s in slots:
                db_player = await plugin.model.api.get_player_by_steam(s)
                
                discord_username = "Desconocido"
                if db_player and db_player.get("discord_id"):
                    discord_id = db_player.get("discord_id")
                    try:
                        user = await ctx.app.rest.fetch_user(int(discord_id))
                        discord_username = user.username
                    except:
                        discord_username = f"ID: {discord_id}"
                        
                steam_name = steam_profiles.get(s, {}).get("personaname", "Desconocido")
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
        await ctx.defer(ephemeral=True)
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
        await ctx.defer(ephemeral=True)
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
        await ctx.defer(ephemeral=True)
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
server_group = crescent.Group("server", description="Administración general del servidor", hooks=[admin_only])

@plugin.include
@server_group.child
@crescent.command(name="announce", description="Envía un anuncio al servidor RCON")
class ServerAnnounce:
    message = crescent.option(str, "Mensaje a enviar")
    
    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer(ephemeral=True)
        try:
            await plugin.model.api.broadcast(self.message)
            await ctx.respond(f"✅ Anuncio enviado:\n> {self.message}")
        except Exception as e:
            await ctx.respond(f"❌ Error al consultar RCON: {e}")

@plugin.include
@crescent.hook(admin_only)
@crescent.command(name="quotas", description="Revisar la ocupación de cupos de las membresías")
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
@crescent.command(name="set_quota", description="Configurar el límite de un tipo de membresía")
class SetQuota:
    membership_type = crescent.option(str, "El tipo exacto de membresía (ej. NITRO, VIP, FUNDADOR)")
    max_quota = crescent.option(int, "Límite máximo (Pon 0 o déjalo vacío para infinito)", default=0)
    
    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer(ephemeral=True)
        try:
            limit = self.max_quota if self.max_quota > 0 else None
            await plugin.model.api.update_quota(self.membership_type.upper(), limit)
            
            limit_str = str(limit) if limit is not None else "Infinito"
            await ctx.respond(f"✅ Cupo para `{self.membership_type.upper()}` configurado a **{limit_str}**.")
        except Exception as e:
            await ctx.respond(f"❌ Error al configurar cupo: {e}")

@plugin.include
@server_group.child
@crescent.command(name="set_max_reserved", description="Modifica el límite máximo de slots reservados (ServerSettings.ini)")
class ServerSetMaxReserved:
    cantidad = crescent.option(int, "Cantidad máxima de slots reservados (0-128)")
    
    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer(ephemeral=True)
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
@crescent.command(name="sync_memberships", description="[DEV] Otorga membresías a usuarios vinculados basándose en sus roles de Discord")
class ForceSyncRolesToMemberships:
    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer(ephemeral=True)
        configs = await plugin.model.api.get_bot_configs()
        role_maps = {} # role_id_str -> db_type
        
        for key, value in configs.items():
            if key.startswith("ROLE_MAP_"):
                db_type = key.replace("ROLE_MAP_", "")
                role_maps[value] = db_type
                
        if not role_maps:
            await ctx.respond("ℹ️ No hay mapeos de roles configurados en /config map_membership_role.")
            return
            
        # Get all linked players (up to 1000 for testing)
        res = await plugin.model.api.get_paginated_players(page=1, limit=1000, linked="all")
        players = res.get("players", [])
        
        if not players:
            await ctx.respond("ℹ️ No hay jugadores vinculados en la base de datos.")
            return
            
        imported = 0
        guild_id = ctx.guild_id
        if not guild_id:
            await ctx.respond("❌ Este comando debe usarse en un servidor.")
            return
            
        skipped = 0
        for p in players:
            discord_id = p.get("discord_id")
            steam_id = p.get("steam_id")
            if not discord_id or not steam_id:
                logger.info(f"[ForceSync] Saltando jugador sin discord_id o steam_id: {p}")
                continue
                
            try:
                member = await plugin.app.rest.fetch_member(guild_id, int(discord_id))
            except Exception as e:
                logger.info(f"[ForceSync] No se pudo obtener member para discord_id {discord_id}: {e}")
                continue
                
            member_role_ids = [str(r) for r in member.role_ids]
            logger.info(f"[ForceSync] Jugador {discord_id} tiene roles: {member_role_ids}")
            
            for role_id_str, db_type in role_maps.items():
                if role_id_str in member_role_ids:
                    try:
                        # Call add_membership without days to use default config
                        await plugin.model.api.add_membership(steam_id, db_type)
                        logger.info(f"[ForceSync] Otorgada membresía {db_type} a steam_id {steam_id}")
                        imported += 1
                    except Exception as e:
                        if "Membership already active" in str(e):
                            skipped += 1
                            logger.info(f"[ForceSync] Omitido: {steam_id} ya tiene membresía activa.")
                        else:
                            logger.error(f"[ForceSync] Falló add_membership para {steam_id}: {e}")
                        
        msg = f"✅ Sincronización completada. Se otorgaron {imported} membresías nuevas."
        if skipped > 0:
            msg += f"\n⚠️ Se omitieron {skipped} membresías porque los usuarios ya la tenían activa."
            
        await ctx.respond(msg)

import time

@plugin.include
@crescent.hook(admin_only)
@crescent.command(name="monitor_hacker", description="Monitorea a un jugador para detectar hacks usando KPM")
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
@crescent.command(name="ban", description="Banea a un jugador por Steam ID y sincroniza con RCON")
class BanPlayer:
    steam_id = crescent.option(str, "Steam ID a banear")
    reason = crescent.option(str, "Razón del ban", default="No especificado")
    
    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer(ephemeral=True)
        try:
            await plugin.model.api.ban_player(str(self.steam_id), str(self.reason))
            await ctx.respond(f"✅ Jugador `{self.steam_id}` ha sido baneado permanentemente en la base de datos y RCON. Razón: {self.reason}")
        except Exception as e:
            await ctx.respond(f"❌ Error al banear: {e}")

@plugin.include
@crescent.hook(admin_only)
@crescent.command(name="unban", description="Desbanea a un jugador por Steam ID y sincroniza con RCON")
class UnbanPlayer:
    steam_id = crescent.option(str, "Steam ID a desbanear")
    
    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer(ephemeral=True)
        try:
            await plugin.model.api.unban_player(str(self.steam_id))
            await ctx.respond(f"✅ Jugador `{self.steam_id}` ha sido desbaneado y sincronizado con RCON.")
        except Exception as e:
            await ctx.respond(f"❌ Error al desbanear: {e}")

@plugin.include
@crescent.hook(admin_only)
@crescent.command(name="compensar_todos", description="Extiende todas las membresías activas por la cantidad de días indicados")
class CompensarTodos:
    dias = crescent.option(int, "Cantidad de días a extender")
    
    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer(ephemeral=True)
        try:
            res = await plugin.model.api.compensate_memberships(self.dias)
            msg = res.get("message", "Compensación completada.")
            await ctx.respond(f"✅ {msg}")
        except Exception as e:
            await ctx.respond(f"❌ Error al compensar: {e}")

@plugin.include
@crescent.hook(admin_only)
@crescent.command(name="extender_membresia", description="Extiende una membresía individual por ID")
class ExtenderMembresia:
    membership_id = crescent.option(int, "ID numérico de la membresía")
    dias = crescent.option(int, "Cantidad de días extra")
    
    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer(ephemeral=True)
        try:
            await plugin.model.api.edit_membership(membership_id=self.membership_id, add_days=self.dias)
            await ctx.respond(f"✅ Membresía #{self.membership_id} extendida por {self.dias} días exitosamente.")
        except Exception as e:
            await ctx.respond(f"❌ Error al extender membresía: {e}")
