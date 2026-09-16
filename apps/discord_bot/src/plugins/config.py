import crescent
import hikari
from src.model import Model
from src.hooks import admin_only
from src.groups import config_group, vip_role_group, role_map_group, whitelist_group, ban_role_group

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

@plugin.include
@crescent.hook(admin_only)
@config_group.child
@crescent.command(name="admin_role", description="Configura el rol de Administrador principal")
class ConfigAdminRole:
    admin_role = crescent.option(hikari.Role, "Rol de Administrador")

    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer(ephemeral=True)
        await plugin.model.api.set_bot_config("ADMIN_ROLE_ID", str(self.admin_role.id))
        await ctx.respond(f"✅ Rol de Administrador configurado a <@&{self.admin_role.id}>")

@plugin.include
@crescent.hook(admin_only)
@vip_role_group.child
@crescent.command(name="add", description="Añade un rol a la lista de roles VIP permitidos")
class AddVipRole:
    vip_role = crescent.option(hikari.Role, "Rol VIP a añadir")

    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer(ephemeral=True)
        
        current_vips = await plugin.model.api.get_bot_config("VIP_ROLE_IDS")
        vip_list = current_vips.split(",") if current_vips else []
        
        role_id_str = str(self.vip_role.id)
        if role_id_str not in vip_list:
            vip_list.append(role_id_str)
            await plugin.model.api.set_bot_config("VIP_ROLE_IDS", ",".join(vip_list))
            await ctx.respond(f"✅ Añadido <@&{self.vip_role.id}> a la lista de roles VIP.")
        else:
            await ctx.respond(f"⚠️ El rol <@&{self.vip_role.id}> ya estaba en la lista de VIPs.")

@plugin.include
@crescent.hook(admin_only)
@vip_role_group.child
@crescent.command(name="remove", description="Elimina un rol de la lista de VIPs")
class RemoveVipRole:
    vip_role = crescent.option(hikari.Role, "Rol VIP a remover")

    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer(ephemeral=True)
        
        current_vips = await plugin.model.api.get_bot_config("VIP_ROLE_IDS")
        vip_list = current_vips.split(",") if current_vips else []
        
        role_id_str = str(self.vip_role.id)
        if role_id_str in vip_list:
            vip_list.remove(role_id_str)
            await plugin.model.api.set_bot_config("VIP_ROLE_IDS", ",".join(vip_list))
            await ctx.respond(f"✅ Removido <@&{self.vip_role.id}> de la lista de roles VIP.")
        else:
            await ctx.respond(f"⚠️ El rol <@&{self.vip_role.id}> no estaba en la lista de VIPs.")

@plugin.include
@crescent.hook(admin_only)
@vip_role_group.child
@crescent.command(name="list", description="Muestra la lista actual de roles VIP configurados")
class ListVipRoles:
    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer(ephemeral=True)
        current_vips = await plugin.model.api.get_bot_config("VIP_ROLE_IDS")
        if not current_vips:
            await ctx.respond("📋 Actualmente no hay roles VIP configurados.")
            return
            
        vip_list = current_vips.split(",")
        
        # Obtener mapeos
        configs = await plugin.model.api.get_bot_configs()
        role_maps = {}
        for key, value in configs.items():
            if key.startswith("ROLE_MAP_"):
                db_type = key.replace("ROLE_MAP_", "")
                if value not in role_maps:
                    role_maps[value] = []
                role_maps[value].append(db_type)
        
        mentions = []
        for r in vip_list:
            if not r: continue
            mapped_types = role_maps.get(str(r), [])
            mapped_str = f" *(Mapeado a: {', '.join(mapped_types)})*" if mapped_types else " *(No mapeado en BD)*"
            mentions.append(f"- <@&{r}>{mapped_str}")
            
        mentions_text = "\n".join(mentions)
        await ctx.respond(f"📋 **Roles VIP Configurados:**\n{mentions_text}")

@plugin.include
@crescent.hook(admin_only)
@role_map_group.child
@crescent.command(name="add", description="Mapea un tipo de membresía de BD a un rol de Discord")
class MapMembershipRole:
    db_type = crescent.option(str, "Tipo en Base de Datos (ej. VIP_EXPRESS)")
    discord_role = crescent.option(hikari.Role, "Rol de Discord a asignar automáticamente")
    default_days = crescent.option(int, "Dias por defecto al otorgar (0 = permanente)", default=30)

    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer(ephemeral=True)
        key_map = f"ROLE_MAP_{self.db_type.upper()}"
        key_days = f"ROLE_DAYS_{self.db_type.upper()}"
        await plugin.model.api.set_bot_config(key_map, str(self.discord_role.id))
        await plugin.model.api.set_bot_config(key_days, str(self.default_days))
        await ctx.respond(f"✅ Mapeo configurado: La membresía {self.db_type.upper()} otorgará el rol <@&{self.discord_role.id}> con una duración base de {self.default_days} días.")

@plugin.include
@crescent.hook(admin_only)
@role_map_group.child
@crescent.command(name="remove", description="Elimina el mapeo de un tipo de membresía")
class UnmapMembershipRole:
    db_type = crescent.option(str, "Tipo en Base de Datos (ej. VIP_EXPRESS)")

    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer(ephemeral=True)
        key_map = f"ROLE_MAP_{self.db_type.upper()}"
        key_days = f"ROLE_DAYS_{self.db_type.upper()}"
        await plugin.model.api.delete_bot_config(key_map)
        await plugin.model.api.delete_bot_config(key_days)
        await ctx.respond(f"✅ Mapeo eliminado para la membresía {self.db_type.upper()}.")

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
