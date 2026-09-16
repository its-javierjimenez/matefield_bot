with open("apps/discord_bot/src/plugins/config.py", "r", encoding="utf-8") as f:
    content = f.read()

import re

# Add ban_role_group import
content = content.replace("from src.groups import config_group, vip_role_group, role_map_group, whitelist_group", "from src.groups import config_group, vip_role_group, role_map_group, whitelist_group, ban_role_group")

# Add the commands
new_commands = """
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
            
        await ctx.respond("**Roles de Baneos:**\n" + "\n".join(lines))
"""

if "@ban_role_group.child" not in content:
    content += new_commands
    with open("apps/discord_bot/src/plugins/config.py", "w", encoding="utf-8") as f:
        f.write(content)
    print("Added ban_role commands to config.py")
