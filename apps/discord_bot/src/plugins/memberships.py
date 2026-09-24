import asyncio
import logging
import time
import crescent
import hikari

from src.model import Model
from src.hooks import admin_only
from src.groups import membership_group, membership_type_group

logger = logging.getLogger(__name__)
plugin = crescent.Plugin[hikari.GatewayBot, Model]()

_cached_types: list[dict] = []
_last_types_fetch: float = 0.0

async def get_cached_membership_types() -> list[dict]:
    global _cached_types, _last_types_fetch
    now = time.time()
    if now - _last_types_fetch > 30 or not _cached_types:
        try:
            _cached_types = await plugin.model.api.get_membership_types(active_only=True)
            _last_types_fetch = now
        except Exception:
            pass
    return _cached_types

async def autocomplete_tipo(
    ctx: crescent.AutocompleteContext, option: hikari.AutocompleteInteractionOption
) -> list[tuple[str, str]]:
    val = str(option.value or "").lower()
    try:
        types = await get_cached_membership_types()
        results = []
        for t in types:
            code = t.get("code", "")
            name = t.get("name", code)
            price = t.get("price_usd", 0.0)
            price_str = f" (${price})" if price > 0 else ""
            label = f"{name} [{code}]{price_str}"[:100]
            if val in code.lower() or val in name.lower():
                results.append((label, code))
        if results:
            return results[:25]
    except Exception:
        pass
    fallback = ["VIP_COMUN", "VIP_EXPRESS", "VIP_PERMANENTE"]
    return [(t, t) for t in fallback if val in t.lower()]


# -------------------------------------------------------------
# Membership Management Commands (/membership ...)
# -------------------------------------------------------------

@plugin.include
@membership_group.child
@crescent.command(name="add", description="Añade una membresía VIP a un jugador vinculado")
class DbAddMembership:
    usuario = crescent.option(hikari.User, "Usuario de Discord a añadir membresía")
    tipo = crescent.option(
        str,
        "Tipo de membresía a otorgar (autocompletado o escribe uno)",
        autocomplete=autocomplete_tipo
    )
    dias = crescent.option(int, "Duración en días (opcional, sobreescribe default del paquete, 0 = permanente)", default=None)
    rol_especial = crescent.option(
        hikari.Role,
        "Rol especial adicional a asignar (opcional, si se omite usa el del paquete)",
        default=None
    )
    booster = crescent.option(
        bool,
        "¿Es Booster de Discord? (opcional: si se omite, se autodetecta)",
        default=None
    )
    servidor = crescent.option(
        int,
        "ID de servidor RCON específico (opcional: si se omite usa el del paquete)",
        default=None
    )

    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer()
        try:
            player_info = await plugin.model.api.get_player_by_discord(str(self.usuario.id))
            if not player_info:
                await ctx.respond("❌ Este usuario no tiene una cuenta de Steam enlazada en la base de datos.")
                return
                
            steam_id = player_info.get("steam_id")
            if not steam_id:
                await ctx.respond("❌ La cuenta no tiene Steam ID asociado.")
                return
                
            is_booster_val = self.booster
            if is_booster_val is None:
                try:
                    if ctx.guild_id:
                        member = await ctx.app.rest.fetch_member(ctx.guild_id, self.usuario.id)
                        is_booster_val = member.premium_since is not None
                    else:
                        is_booster_val = False
                except Exception:
                    is_booster_val = False

            special_role = str(self.rol_especial.id) if self.rol_especial else None
            await plugin.model.api.add_membership(
                str(steam_id),
                str(self.tipo),
                self.dias,
                special_role,
                is_booster=is_booster_val,
                server_id=self.servidor
            )
            
            if self.dias is None:
                dias_str = "Predeterminado (paquete)"
            elif self.dias == 0:
                dias_str = "Permanente"
            else:
                dias_str = f"{self.dias} días"
            booster_tag = "⚡ **Booster:** Sí" if is_booster_val else "⚡ **Booster:** No"
            server_tag = f"🌐 **Servidor:** #{self.servidor}" if self.servidor else "🌐 **Alcance:** Global"
            msg = f"✅ Membresía {self.tipo} añadida a <@{self.usuario.id}> ({steam_id})\n⏳ **Duración:** {dias_str} | {booster_tag} | {server_tag}"
            if special_role:
                msg += f"\n(Rol especial <@&{special_role}> asignado en base de datos)"
            await ctx.respond(msg)
        except Exception as e:
            await ctx.respond(f"❌ Error: {e}")


@plugin.include
@crescent.hook(admin_only)
@membership_group.child
@crescent.command(name="list", description="Listado de membresías (Paginado)")
class DbMemberships:
    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer(ephemeral=True)
        page = 1
        try:
            res = await plugin.model.api.get_paginated_memberships(page=page, limit=10)
            memberships = res.get("memberships", [])
            total = res.get("total", 0)
            
            if not memberships:
                await ctx.respond("No hay membresías registradas.")
                return
                
            embed = hikari.Embed(
                title=f"📋 Listado de Membresías (Pág {page})",
                description=f"Total registradas: {total}",
                color=0x00FF00
            )
            
            for m in memberships:
                status = "🟢 Activa" if m['is_active'] else "🔴 Inactiva"
                booster_str = " | ⚡ **Booster**" if m.get('is_booster') else ""
                end_str = m['end_date'][:10] if m['end_date'] else "Permanente"
                sp_str = f" | **Especial:** <@&{m.get('special_role')}>" if m.get('special_role') else ""
                embed.add_field(
                    name=f"[ID: {m.get('id', '?')}] SteamID: {m['steam_id']}", 
                    value=f"**Tipo:** {m['type']} | **Estado:** {status}{booster_str}\n**Vence:** {end_str}{sp_str}", 
                    inline=False
                )
                
            components = [
                ctx.app.rest.build_message_action_row()
                .add_interactive_button(hikari.ButtonStyle.PRIMARY, f"mem_prev_{page}", label="Anterior")
                .add_interactive_button(hikari.ButtonStyle.PRIMARY, f"mem_next_{page}", label="Siguiente")
            ]
            
            await ctx.respond(embed=embed, components=components)
        except Exception as e:
            await ctx.respond(f"❌ Error: {e}")


@plugin.include
@crescent.event
async def on_membership_button_click(event: hikari.InteractionCreateEvent) -> None:
    if not isinstance(event.interaction, hikari.ComponentInteraction):
        return
        
    custom_id = event.interaction.custom_id
    if not custom_id.startswith("mem_prev_") and not custom_id.startswith("mem_next_"):
        return
        
    current_page = int(custom_id.split("_")[-1])
    is_next = custom_id.startswith("mem_next_")
    new_page = current_page + 1 if is_next else current_page - 1
    
    if new_page < 1:
        new_page = 1
        
    try:
        res = await plugin.model.api.get_paginated_memberships(page=new_page, limit=10)
        memberships = res.get("memberships", [])
        total = res.get("total", 0)
        
        if not memberships and new_page > 1:
            await event.interaction.create_initial_response(
                hikari.ResponseType.MESSAGE_CREATE,
                "No hay más páginas.",
                flags=hikari.MessageFlag.EPHEMERAL
            )
            return
            
        embed = hikari.Embed(
            title=f"📋 Listado de Membresías (Pág {new_page})",
            description=f"Total registradas: {total}",
            color=0x00FF00
        )
        
        for m in memberships:
            status = "🟢 Activa" if m['is_active'] else "🔴 Inactiva"
            booster_str = " | ⚡ **Booster**" if m.get('is_booster') else ""
            end_str = m['end_date'][:10] if m['end_date'] else "Permanente"
            sp_str = f" | **Especial:** <@&{m.get('special_role')}>" if m.get('special_role') else ""
            embed.add_field(
                name=f"[ID: {m.get('id', '?')}] SteamID: {m['steam_id']}", 
                value=f"**Tipo:** {m['type']} | **Estado:** {status}{booster_str}\n**Vence:** {end_str}{sp_str}", 
                inline=False
            )
            
        components = [
            plugin.app.rest.build_message_action_row()
            .add_interactive_button(hikari.ButtonStyle.PRIMARY, f"mem_prev_{new_page}", label="Anterior")
            .add_interactive_button(hikari.ButtonStyle.PRIMARY, f"mem_next_{new_page}", label="Siguiente")
        ]
        
        await event.interaction.create_initial_response(
            hikari.ResponseType.MESSAGE_UPDATE,
            embed=embed,
            components=components
        )
    except Exception as e:
        await event.interaction.create_initial_response(
            hikari.ResponseType.MESSAGE_CREATE,
            f"❌ Error: {e}",
            flags=hikari.MessageFlag.EPHEMERAL
        )


@plugin.include
@crescent.hook(admin_only)
@membership_group.child
@crescent.command(name="edit", description="Edita una membresía existente")
class DbEditMembership:
    id_membresia = crescent.option(int, "ID de la membresía (ver /membership list)")
    dias = crescent.option(int, "Nuevos días (0 = permanente)", default=None, min_value=0)
    tipo = crescent.option(str, "Nuevo tipo de membresía", autocomplete=autocomplete_tipo, default=None)
    activa = crescent.option(bool, "¿Está activa?", default=None)
    booster = crescent.option(bool, "¿Es Booster de Discord?", default=None)

    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer()
        try:
            await plugin.model.api.edit_membership(
                int(self.id_membresia),
                days=self.dias,
                membership_type=str(self.tipo) if self.tipo else None,
                is_active=self.activa,
                is_booster=self.booster
            )
            await ctx.respond(f"✅ Membresía ID {self.id_membresia} actualizada exitosamente.")
        except Exception as e:
            await ctx.respond(f"❌ Error: {e}")


@plugin.include
@crescent.hook(admin_only)
@membership_group.child
@crescent.command(name="remove", description="Elimina una membresía existente permanentemente")
class DbRemoveMembership:
    id_membresia = crescent.option(int, "ID de la membresía (ver /membership list)")

    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer()
        try:
            await plugin.model.api.delete_membership(self.id_membresia)
            await ctx.respond(f"✅ Membresía ID {self.id_membresia} eliminada exitosamente.")
        except Exception as e:
            await ctx.respond(f"❌ Error: {e}")


@plugin.include
@crescent.hook(admin_only)
@membership_group.child
@crescent.command(name="export", description="Exporta las membresías y cuentas vinculadas a un CSV descargable")
class DbExportMemberships:
    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer(ephemeral=True)
        try:
            res = await plugin.model.api.export_memberships()
            download_url = res["download_url"]
            total = res["total_records"]
            filename = res["filename"]
            expires_mins = res["expires_in_seconds"] // 60
            size_kb = round(res["size_bytes"] / 1024, 1)

            embed = hikari.Embed(
                title="📥 Exportación de Membresías",
                description=(
                    f"Se ha generado exitosamente el archivo CSV con las membresías y cuentas vinculadas.\n\n"
                    f"🔗 **[Haz clic aquí para descargar el archivo CSV]({download_url})**\n\n"
                    f"*(El enlace es de descarga directa desde la API y expira en {expires_mins} minutos para mayor seguridad)*"
                ),
                color=0x00FF88
            )
            embed.add_field(name="📄 Archivo", value=filename, inline=True)
            embed.add_field(name="👥 Total Membresías", value=str(total), inline=True)
            embed.add_field(name="📦 Tamaño", value=f"{size_kb} KB", inline=True)
            embed.add_field(
                name="🛡️ Columnas incluidas",
                value="DiscordID, SteamID, Nickname, Tipo VIP, Booster, Fundador, Rol Vinculado, Vigencia y Observaciones.",
                inline=False
            )

            button_row = (
                ctx.app.rest.build_message_action_row()
                .add_link_button(download_url, label="Descargar CSV")
            )
            await ctx.respond(embed=embed, components=[button_row])
        except Exception as e:
            await ctx.respond(f"❌ Error al generar exportación: {e}")


@plugin.include
@crescent.hook(admin_only)
@membership_group.child
@crescent.command(name="sync", description="[DEV] Otorga membresías a usuarios vinculados basándose en sus roles de Discord")
class ForceSyncRolesToMemberships:
    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer()
        configs = await plugin.model.api.get_bot_configs()
        role_maps = {} # role_id_str -> db_type
        
        for key, value in configs.items():
            if key.startswith("ROLE_MAP_"):
                db_type = key.replace("ROLE_MAP_", "")
                role_maps[value] = db_type
                
        if not role_maps:
            await ctx.respond("ℹ️ No hay mapeos de roles configurados en /config map_membership_role.")
            return
            
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


@plugin.include
@crescent.hook(admin_only)
@membership_group.child
@crescent.command(name="compensate_all", description="Extiende todas las membresías activas por la cantidad de días indicados")
class CompensarTodos:
    dias = crescent.option(int, "Cantidad de días a extender")
    
    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer()
        try:
            res = await plugin.model.api.compensate_memberships(self.dias)
            msg = res.get("message", "Compensación completada.")
            await ctx.respond(f"✅ {msg}")
        except Exception as e:
            await ctx.respond(f"❌ Error al compensar: {e}")


@plugin.include
@crescent.hook(admin_only)
@membership_group.child
@crescent.command(name="extend", description="Extiende una membresía individual por ID")
class ExtenderMembresia:
    membership_id = crescent.option(int, "ID numérico de la membresía")
    dias = crescent.option(int, "Cantidad de días extra")
    
    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer()
        try:
            await plugin.model.api.edit_membership(membership_id=self.membership_id, add_days=self.dias)
            await ctx.respond(f"✅ Membresía #{self.membership_id} extendida por {self.dias} días exitosamente.")
        except Exception as e:
            await ctx.respond(f"❌ Error al extender membresía: {e}")


# -------------------------------------------------------------
# Membership Types Management Commands (/membership_type ...)
# -------------------------------------------------------------

@plugin.include
@crescent.hook(admin_only)
@membership_type_group.child
@crescent.command(name="list", description="Lista todos los paquetes y tipos de membresía configurados")
class DbMembershipTypeList:
    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer()
        try:
            types = await plugin.model.api.get_membership_types()
            if not types:
                await ctx.respond("ℹ️ No hay tipos de membresía registrados.")
                return

            embed = hikari.Embed(
                title="📦 Catálogo de Tipos de Membresía / Paquetes",
                color=0x3498DB,
                description="Listado de paquetes configurados con cupos, precios y alcance de servidor."
            )

            for t in types:
                code = t.get("code", "")
                name = t.get("name", code)
                price = t.get("price_usd", 0.0)
                billing = "Mensualidad" if t.get("billing_type") == "RECURRING" else "Pago Único"
                days = t.get("default_days", 30)
                days_str = "Permanente" if days == 0 else f"{days} días"
                max_q = t.get("max_quota")
                used_q = t.get("current_usage", 0)
                quota_str = f"{used_q}/{max_q}" if max_q is not None else f"{used_q} (Ilimitado)"
                server_name = t.get("server_name", "Global (Todos)")
                role_id = t.get("discord_role_id")
                role_str = f"<@&{role_id}>" if role_id else "Ninguno"
                status_icon = "🟢" if t.get("is_active", True) else "🔴 (Inactivo)"

                field_value = (
                    f"💵 **Precio:** ${price:.2f} USD ({billing})\n"
                    f"⏳ **Duración:** {days_str}\n"
                    f"👥 **Cupos Activos:** {quota_str}\n"
                    f"🌐 **Servidor:** {server_name}\n"
                    f"🛡️ **Rol Discord:** {role_str}\n"
                    f"🏷️ **Estado:** {status_icon}"
                )
                embed.add_field(name=f"#{t.get('id')} - {name} (`{code}`)", value=field_value, inline=True)

            await ctx.respond(embed=embed)
        except Exception as e:
            await ctx.respond(f"❌ Error al consultar tipos de membresía: {e}")


@plugin.include
@crescent.hook(admin_only)
@membership_type_group.child
@crescent.command(name="create", description="Crea un nuevo paquete o tipo de membresía")
class DbMembershipTypeCreate:
    codigo = crescent.option(str, "Código único (ej: VIP_GOLD, VIP_SERVER1)")
    nombre = crescent.option(str, "Nombre amigable (ej: VIP Oro Global)")
    precio = crescent.option(float, "Precio en USD (ej: 9.99)", default=0.0)
    dias = crescent.option(int, "Días de duración por defecto (0 = permanente)", default=30)
    cupo = crescent.option(int, "Cupo máximo simultáneo (opcional: dejar vacío o 0 para ilimitado)", default=0)
    rol = crescent.option(hikari.Role, "Rol de Discord a asignar automáticamente (opcional)", default=None)
    servidor = crescent.option(int, "ID de servidor RCON específico (opcional: vacío = Global)", default=None)
    facturacion = crescent.option(
        str,
        "Modalidad de cobro",
        choices=(
            ("Pago Único", "ONE_TIME"),
            ("Mensualidad Recurrente", "RECURRING"),
        ),
        default="ONE_TIME"
    )
    descripcion = crescent.option(str, "Descripción del paquete (opcional)", default=None)

    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer()
        try:
            max_q = self.cupo if self.cupo and self.cupo > 0 else None
            role_id = str(self.rol.id) if self.rol else None
            res = await plugin.model.api.create_membership_type(
                code=self.codigo,
                name=self.nombre,
                description=self.descripcion,
                price_usd=self.precio,
                billing_type=str(self.facturacion),
                default_days=self.dias,
                max_quota=max_q,
                discord_role_id=role_id,
                server_id=self.servidor
            )
            msg = res.get("message", "Tipo de membresía creado.")
            await ctx.respond(f"✅ {msg}")
        except Exception as e:
            await ctx.respond(f"❌ Error al crear tipo de membresía: {e}")


@plugin.include
@crescent.hook(admin_only)
@membership_type_group.child
@crescent.command(name="edit", description="Edita los parámetros de un paquete o tipo de membresía existente")
class DbMembershipTypeEdit:
    tipo_id = crescent.option(int, "ID numérico del tipo de membresía a editar")
    nombre = crescent.option(str, "Nuevo nombre comercial (opcional)", default=None)
    precio = crescent.option(float, "Nuevo precio en USD (opcional)", default=None)
    dias = crescent.option(int, "Nuevos días por defecto (0 = permanente, opcional)", default=None)
    cupo = crescent.option(int, "Nuevo cupo máximo (0 para ilimitado, opcional)", default=None)
    rol = crescent.option(hikari.Role, "Nuevo rol de Discord a vincular (opcional)", default=None)
    servidor = crescent.option(int, "Nuevo ID de servidor RCON (opcional)", default=None)
    facturacion = crescent.option(
        str,
        "Nueva modalidad de cobro (opcional)",
        choices=(
            ("Pago Único", "ONE_TIME"),
            ("Mensualidad Recurrente", "RECURRING"),
        ),
        default=None
    )
    activo = crescent.option(bool, "¿Activar o desactivar este paquete? (opcional)", default=None)

    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer()
        try:
            kwargs = {}
            if self.nombre is not None:
                kwargs["name"] = self.nombre
            if self.precio is not None:
                kwargs["price_usd"] = self.precio
            if self.dias is not None:
                kwargs["default_days"] = self.dias
            if self.cupo is not None:
                kwargs["max_quota"] = self.cupo if self.cupo > 0 else None
            if self.rol is not None:
                kwargs["discord_role_id"] = str(self.rol.id)
            if self.servidor is not None:
                kwargs["server_id"] = self.servidor
            if self.facturacion is not None:
                kwargs["billing_type"] = str(self.facturacion)
            if self.activo is not None:
                kwargs["is_active"] = self.activo

            if not kwargs:
                await ctx.respond("⚠️ No especificaste ningún campo para actualizar.")
                return

            res = await plugin.model.api.update_membership_type(self.tipo_id, **kwargs)
            msg = res.get("message", "Tipo de membresía actualizado.")
            await ctx.respond(f"✅ {msg}")
        except Exception as e:
            await ctx.respond(f"❌ Error al actualizar tipo de membresía: {e}")
