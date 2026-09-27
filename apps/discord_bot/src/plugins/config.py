import logging
import asyncio
import crescent
import hikari
from src.model import Model
from src.hooks import admin_only
from src.groups import config_group, roles_group, whitelist_group, ban_role_group, role_group

logger = logging.getLogger(__name__)

plugin = crescent.Plugin[hikari.GatewayBot, Model]()

@plugin.include
@crescent.hook(admin_only)
@config_group.child
@crescent.command(name="announcement_channel", description="Configura el canal de anuncios (Admin)")
class ConfigChannel:
    channel = crescent.option(hikari.TextableGuildChannel, "El canal donde enviar anuncios de RCON")

    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer(ephemeral=True)
        await plugin.model.api.set_bot_config("ANNOUNCEMENT_CHANNEL_ID", str(self.channel.id))
        await ctx.respond(f"✅ Canal de anuncios configurado a <#{self.channel.id}>")


async def autocomplete_role_type(
    ctx: crescent.AutocompleteContext, option: hikari.AutocompleteInteractionOption
) -> list[tuple[str, str]]:
    standard_types = ["SYSTEM", "VIP", "SPECIAL", "PUBLIC"]
    val = str(option.value or "").strip().upper()
    results = []
    if val and val not in standard_types:
        results.append((f"Personalizado: {val}", val))
    for t in standard_types:
        if not val or val in t:
            results.append((f"{t} (Estándar)", t))
    return results[:25]


async def autocomplete_db_roles(
    ctx: crescent.AutocompleteContext, option: hikari.AutocompleteInteractionOption
) -> list[tuple[str, str]]:
    """Autocompleta roles registrados en la Base de Datos (DDD)."""
    val = str(option.value or "").strip().lower()
    try:
        roles = await plugin.model.api.get_all_roles()
        results = []
        for r in roles:
            code = r.get("code", "")
            name = r.get("name", code)
            rtype = r.get("role_type", "")
            label = f"{name} ({code}) [{rtype}]"[:100]
            if not val or val in code.lower() or val in name.lower() or val in rtype.lower():
                results.append((label, code))
        return results[:25]
    except Exception:
        return []


@plugin.include
@crescent.hook(admin_only)
@roles_group.child
@crescent.command(name="register", description="Registra o actualiza un rol en la Base de Datos (DDD)")
class RegisterRole:
    code = crescent.option(str, "Código único del Rol (ej. VIP_EXPRESS, MASTERCHEF)")
    name = crescent.option(str, "Nombre descriptivo del Rol")
    role_type = crescent.option(str, "Tipo de rol (estándar o personalizado)", autocomplete=autocomplete_role_type)
    discord_role = crescent.option(hikari.Role, "Rol de Discord a asociar")

    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer(ephemeral=True)
        try:
            norm_type = self.role_type.strip().upper()
            await plugin.model.api.register_role(
                code=self.code.upper(),
                name=self.name,
                role_type=norm_type,
                discord_role_id=str(self.discord_role.id)
            )
            await ctx.respond(f"✅ Rol `{self.code.upper()}` registrado como `{norm_type}` y asociado a <@&{self.discord_role.id}>.")
        except Exception as e:
            await ctx.respond(f"❌ Error al registrar rol: {e}")

@plugin.include
@crescent.hook(admin_only)
@roles_group.child
@crescent.command(name="list", description="Lista todos los roles registrados en la Base de Datos")
class ListRoles:
    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer(ephemeral=True)
        try:
            roles = await plugin.model.api.get_all_roles()
            if not roles:
                await ctx.respond("No hay roles registrados.")
                return
            
            msg = "**Roles Registrados (DDD):**\n"
            for r in roles:
                msg += f"- `{r.get('code')}` ({r.get('role_type')}): {r.get('name')} -> <@&{r.get('discord_role_id')}>\n"
            await ctx.respond(msg)
        except Exception as e:
            await ctx.respond(f"❌ Error al listar roles: {e}")

@plugin.include
@crescent.hook(admin_only)
@roles_group.child
@crescent.command(name="give", description="Asigna un rol registrado en la Base de Datos a un jugador vinculado")
class GiveRole:
    usuario = crescent.option(hikari.User, "Usuario de Discord a asignar el rol")
    rol = crescent.option(str, "Rol registrado en la Base de Datos", autocomplete=autocomplete_db_roles)

    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer(ephemeral=True)
        try:
            player_info = await plugin.model.api.get_player_by_discord(str(self.usuario.id))
            if not player_info:
                await ctx.respond(f"❌ El usuario {self.usuario.mention} no tiene cuenta vinculada.")
                return
            steam_id = player_info.get("steam_id")
            
            roles = await plugin.model.api.get_all_roles()
            role_obj = next((r for r in roles if r.get("code", "").upper() == self.rol.strip().upper()), None)
            role_code = str(role_obj["code"]) if (role_obj and "code" in role_obj) else self.rol.strip().upper()
            
            await plugin.model.api.add_special_role(str(steam_id), role_code)
            
            discord_msg = ""
            if role_obj and role_obj.get("discord_role_id") and ctx.guild_id:
                try:
                    target_role_id = int(role_obj["discord_role_id"])
                    await ctx.app.rest.add_role_to_member(ctx.guild_id, self.usuario.id, target_role_id)
                    discord_msg = f" y rol de Discord <@&{target_role_id}> otorgado"
                except Exception as d_err:
                    discord_msg = f" (nota: no se pudo asignar rol en Discord inmediatamente: {d_err})"
                    
            await ctx.respond(f"✅ Rol `{role_code}` asignado a {self.usuario.mention} (`{steam_id}`){discord_msg}.")
        except Exception as e:
            await ctx.respond(f"❌ Error al asignar rol: {e}")

@plugin.include
@crescent.hook(admin_only)
@roles_group.child
@crescent.command(name="remove", description="Remueve un rol de la Base de Datos a un jugador vinculado")
class RemoveRole:
    usuario = crescent.option(hikari.User, "Usuario de Discord a remover el rol")
    rol = crescent.option(str, "Rol registrado en la Base de Datos a remover", autocomplete=autocomplete_db_roles)

    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer(ephemeral=True)
        try:
            player_info = await plugin.model.api.get_player_by_discord(str(self.usuario.id))
            if not player_info:
                await ctx.respond(f"❌ El usuario {self.usuario.mention} no tiene cuenta vinculada.")
                return
            steam_id = player_info.get("steam_id")
            
            roles = await plugin.model.api.get_all_roles()
            role_obj = next((r for r in roles if r.get("code", "").upper() == self.rol.strip().upper()), None)
            role_code = str(role_obj["code"]) if (role_obj and "code" in role_obj) else self.rol.strip().upper()
            
            await plugin.model.api.remove_special_role(str(steam_id), role_code)
            
            discord_msg = ""
            if role_obj and role_obj.get("discord_role_id") and ctx.guild_id:
                try:
                    target_role_id = int(role_obj["discord_role_id"])
                    await ctx.app.rest.remove_role_from_member(ctx.guild_id, self.usuario.id, target_role_id)
                    discord_msg = f" y rol de Discord <@&{target_role_id}> removido"
                except Exception as d_err:
                    discord_msg = f" (nota: no se pudo remover rol en Discord inmediatamente: {d_err})"
                    
            await ctx.respond(f"✅ Rol `{role_code}` removido de {self.usuario.mention} (`{steam_id}`){discord_msg}.")
        except Exception as e:
            await ctx.respond(f"❌ Error al remover rol: {e}")

@plugin.include
@crescent.hook(admin_only)
@config_group.child
@crescent.command(name="list", description="Lista todas las configuraciones y mapeos activos")
class ListConfigs:
    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer(ephemeral=True)
        configs = await plugin.model.api.get_bot_configs()
        
        if not configs:
            await ctx.respond("ℹ️ No hay configuraciones activas.")
            return
            
        embed = hikari.Embed(
            title="⚙️ Configuraciones del Bot",
            color=0x00A2E8
        )
        
        for key, value in configs.items():
            if key.startswith("ROLE_MAP_"):
                tipo = key.replace("ROLE_MAP_", "")
                embed.add_field(name=f"Mapeo de Rol: {tipo}", value=f"<@&{value}> (ID: {value})", inline=False)
            else:
                if key.endswith("_ROLE_ID") or key.endswith("_ROLE_IDS"):
                    roles = [f"<@&{r.strip()}>" for r in value.split(",")]
                    val_str = ", ".join(roles)
                else:
                    val_str = value
                embed.add_field(name=key, value=val_str, inline=False)
                
        await ctx.respond(embed=embed)

@plugin.include
@crescent.hook(admin_only)
@whitelist_group.child
@crescent.command(name="add", description="Añade un usuario a la Whitelist para que el bot no le quite roles")
class AddWhitelist:
    usuario = crescent.option(hikari.User, "Usuario de Discord a proteger")

    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer(ephemeral=True)
        
        current_wl = await plugin.model.api.get_bot_config("SYNC_WHITELIST")
        wl_list = current_wl.split(",") if current_wl else []
        
        user_id_str = str(self.usuario.id)
        if user_id_str not in wl_list:
            wl_list.append(user_id_str)
            await plugin.model.api.set_bot_config("SYNC_WHITELIST", ",".join(wl_list))
            await ctx.respond(f"✅ Usuario <@{self.usuario.id}> añadido a la Whitelist de sincronización.")
        else:
            await ctx.respond(f"⚠️ El usuario <@{self.usuario.id}> ya estaba en la Whitelist.")

@plugin.include
@crescent.hook(admin_only)
@whitelist_group.child
@crescent.command(name="remove", description="Remueve un usuario de la Whitelist")
class RemoveWhitelist:
    usuario = crescent.option(hikari.User, "Usuario de Discord a desproteger")

    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer(ephemeral=True)
        
        current_wl = await plugin.model.api.get_bot_config("SYNC_WHITELIST")
        wl_list = current_wl.split(",") if current_wl else []
        
        user_id_str = str(self.usuario.id)
        if user_id_str in wl_list:
            wl_list.remove(user_id_str)
            if wl_list:
                await plugin.model.api.set_bot_config("SYNC_WHITELIST", ",".join(wl_list))
            else:
                await plugin.model.api.delete_bot_config("SYNC_WHITELIST")
            await ctx.respond(f"✅ Usuario <@{self.usuario.id}> removido de la Whitelist.")
        else:
            await ctx.respond(f"⚠️ El usuario <@{self.usuario.id}> no estaba en la Whitelist.")

@plugin.include
@crescent.hook(admin_only)
@whitelist_group.child
@crescent.command(name="list", description="Lista los usuarios en la Whitelist de sincronización")
class ListWhitelist:
    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer(ephemeral=True)
        current_wl = await plugin.model.api.get_bot_config("SYNC_WHITELIST")
        if not current_wl:
            await ctx.respond("ℹ️ Actualmente no hay usuarios en la Whitelist.")
            return
            
        wl_list = current_wl.split(",")
        mentions = "\n".join([f"- <@{u}>" for u in wl_list if u])
        await ctx.respond(f"🛡️ **Usuarios en Whitelist (Protegidos):**\n{mentions}")

@plugin.include
@crescent.hook(admin_only)
@config_group.child
@crescent.command(name="match_channel", description="Configura el canal donde se enviarán los resultados de las partidas")
class SetMatchChannel:
    canal = crescent.option(hikari.TextableChannel, "Canal de Discord")

    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer(ephemeral=True)
        await plugin.model.api.set_bot_config("MATCH_ANNOUNCE_CHANNEL_ID", str(self.canal.id))
        await ctx.respond(f"✅ Canal de resultados configurado exitosamente a <#{self.canal.id}>.")

@plugin.include
@ban_role_group.child
@crescent.command(name="map", description="Mapea una duración de baneo a un rol de Discord")
class MapBanRole:
    dias = crescent.option(int, "Duración en días (0 para permanente)")
    discord_role = crescent.option(hikari.Role, "Rol de Discord a asignar cuando el jugador es baneado")

    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer(ephemeral=True)
        key = f"BAN_ROLE_{self.dias}"
        val = str(self.discord_role.id)
        
        await plugin.model.api.set_bot_config(key, val)
        dur_str = "Permanente" if self.dias == 0 else f"{self.dias} días"
        await ctx.respond(f"? Los baneos de duración **{dur_str}** ahora asignarán el rol <@&{self.discord_role.id}>.")

@plugin.include
@ban_role_group.child
@crescent.command(name="unmap", description="Elimina el mapeo de rol para una duración de baneo")
class UnmapBanRole:
    dias = crescent.option(int, "Duración en días a desmapear (0 para permanente)")

    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer(ephemeral=True)
        key = f"BAN_ROLE_{self.dias}"
        
        await plugin.model.api.delete_bot_config(key)
        dur_str = "Permanente" if self.dias == 0 else f"{self.dias} días"
        await ctx.respond(f"? Se eliminó el mapeo de rol para los baneos de **{dur_str}**.")

@plugin.include
@ban_role_group.child
@crescent.command(name="list", description="Lista los roles asociados a los baneos")
class ListBanRoles:
    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer(ephemeral=True)
        configs = await plugin.model.api.get_bot_configs()
        
        lines = []
        for k, v in configs.items():
            if k.startswith("BAN_ROLE_"):
                dias = k.replace("BAN_ROLE_", "")
                dur_str = "Permanente" if dias == "0" else f"{dias} días"
                lines.append(f"- **{dur_str}**: <@&{v}>")
                
        if not lines:
            await ctx.respond("No hay roles de baneos configurados.")
            return
            
        await ctx.respond("**Roles de Baneos:\n" + "\n".join(lines))


async def _sync_retroactive_link_role(ctx: crescent.Context, guild_id: int, role_id: int) -> tuple[int, int]:
    assigned_count = 0
    already_had_count = 0
    page = 1
    limit = 100
    try:
        while True:
            res = await plugin.model.api.get_paginated_players(page=page, limit=limit, linked="linked")
            players = res.get("players", [])
            if not players:
                break
            for p in players:
                d_id_str = p.get("discord_id")
                if not d_id_str or not d_id_str.isdigit():
                    continue
                try:
                    d_id = int(d_id_str)
                    await asyncio.sleep(0.05)
                    member = plugin.app.cache.get_member(guild_id, d_id)
                    if not member:
                        member = await plugin.app.rest.fetch_member(guild_id, d_id)
                    if member:
                        if role_id not in member.role_ids:
                            await member.add_role(role_id, reason="Rol de vinculación asignado retroactivamente (/role set_link)")
                            assigned_count += 1
                        else:
                            already_had_count += 1
                except hikari.NotFoundError:
                    continue
                except hikari.ForbiddenError as fe:
                    logger.warning(f"Permisos insuficientes para asignar rol {role_id} en guild {guild_id}: {fe}")
                    break
                except Exception as ex:
                    logger.debug(f"No se pudo asignar rol de link a {d_id_str}: {ex}")

            total = res.get("total", 0)
            if len(players) < limit or page * limit >= total:
                break
            page += 1

        summary = f"✅ Rol de vinculación configurado a <@&{role_id}>. Se otorgará automáticamente al usar `/player link`.\n🔗 **Sincronización retroactiva finalizada:** {assigned_count} rol(es) asignado(s)"
        if already_had_count > 0:
            summary += f" ({already_had_count} ya lo tenían)."
        else:
            summary += "."
        try:
            await ctx.edit(content=summary)
        except Exception as edit_err:
            logger.debug(f"No se pudo actualizar mensaje de /role set_link: {edit_err}")
    except Exception as e:
        logger.error(f"Error al sincronizar rol de vinculación retroactivo: {e}")
    return assigned_count, already_had_count


async def _execute_set_link(ctx: crescent.Context, rol: hikari.Role | None) -> asyncio.Task | None:
    await ctx.defer(ephemeral=True)
    if rol:
        if getattr(rol, "is_managed", False) is True:
            await ctx.respond("❌ No se puede asignar un rol administrado por Discord/integraciones.")
            return None

        await plugin.model.api.set_bot_config("LINK_ROLE_ID", str(rol.id))
        if ctx.guild_id:
            await plugin.model.api.set_bot_config("GUILD_ID", str(ctx.guild_id))
        
        if ctx.guild_id:
            await ctx.respond(
                f"✅ Rol de vinculación configurado a <@&{rol.id}>. Se otorgará automáticamente al usar `/player link`.\n"
                f"⏳ Sincronizando usuarios vinculados en este servidor en segundo plano..."
            )
            task = asyncio.create_task(_sync_retroactive_link_role(ctx, ctx.guild_id, rol.id))
            return task
        else:
            await ctx.respond(f"✅ Rol de vinculación configurado a <@&{rol.id}>. Se otorgará automáticamente al usar `/player link`.")
            return None
    else:
        await plugin.model.api.set_bot_config("LINK_ROLE_ID", "")
        await ctx.respond("✅ Rol de vinculación desactivado.")
        return None


@plugin.include
@crescent.hook(admin_only)
@role_group.child
@crescent.command(name="set_link", description="Configura el rol que se otorga automáticamente al vincular la cuenta")
class RoleSetLink:
    rol = crescent.option(hikari.Role, "Rol a asignar al vincular (opcional, omitir para desactivar)", default=None)

    async def callback(self, ctx: crescent.Context) -> asyncio.Task | None:
        return await _execute_set_link(ctx, self.rol)


@plugin.include
@crescent.hook(admin_only)
@roles_group.child
@crescent.command(name="set_link", description="Configura el rol que se otorga automáticamente al vincular la cuenta")
class RolesSetLink:
    rol = crescent.option(hikari.Role, "Rol a asignar al vincular (opcional, omitir para desactivar)", default=None)

    async def callback(self, ctx: crescent.Context) -> asyncio.Task | None:
        return await _execute_set_link(ctx, self.rol)


@plugin.include
@crescent.hook(admin_only)
@role_group.child
@crescent.command(name="set_ban", description="Configura el rol que se otorga automáticamente al banear a un usuario")
class RoleSetBan:
    rol = crescent.option(hikari.Role, "Rol a asignar al banear (opcional, omitir para desactivar)", default=None)

    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer(ephemeral=True)
        if self.rol:
            await plugin.model.api.set_bot_config("BAN_ROLE_DEFAULT", str(self.rol.id))
            await ctx.respond(f"✅ Rol de baneo configurado a <@&{self.rol.id}>. Se otorgará automáticamente al banear con `/ban add`.")
        else:
            await plugin.model.api.set_bot_config("BAN_ROLE_DEFAULT", "")
            await ctx.respond("✅ Rol de baneo desactivado.")


@plugin.include
@crescent.event
async def on_started(event: hikari.StartedEvent) -> None:
    try:
        guilds = list(plugin.app.cache.get_guilds_view())
        if guilds:
            existing = await plugin.model.api.get_bot_config("GUILD_ID")
            if not existing:
                await plugin.model.api.set_bot_config("GUILD_ID", str(guilds[0]))
                logger.info(f"Configurado GUILD_ID primario en BotConfig: {guilds[0]}")
    except Exception as e:
        logger.debug(f"No se pudo inicializar GUILD_ID en startup: {e}")


