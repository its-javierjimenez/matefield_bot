with open("apps/discord_bot/src/plugins/database.py", "r", encoding="utf-8") as f:
    content = f.read()

import re

old_add = """class DbAddSpecialRole:
    steam_id = crescent.option(str, "Steam ID del jugador")
    rol_especial = crescent.option(hikari.Role, "Rol especial a asignar")

    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer()
        try:
            await plugin.model.api.add_special_role(self.steam_id, str(self.rol_especial.id))
            await ctx.respond(f"✅ Rol especial <@&{self.rol_especial.id}> añadido al jugador {self.steam_id}.")
        except Exception as e:
            await ctx.respond(f"❌ Error: {e}")"""

new_add = """class DbAddSpecialRole:
    usuario = crescent.option(hikari.User, "Usuario de Discord") # type: ignore
    rol_especial = crescent.option(str, "Rol especial a asignar en BD", choices=[("ADMIN", "ADMIN"), ("OWNER", "OWNER"), ("VIP", "VIP")]) # type: ignore

    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer()
        try:
            player_info = await plugin.model.api.get_player_by_discord(str(self.usuario.id))
            if not player_info:
                await ctx.respond(f"❌ El usuario {self.usuario.mention} no está vinculado.")
                return
            steam_id = player_info.get("steam_id")
            await plugin.model.api.add_special_role(steam_id, self.rol_especial)
            await ctx.respond(f"✅ Rol especial `{self.rol_especial}` añadido al jugador {self.usuario.mention} (SteamID: {steam_id}).")
        except Exception as e:
            await ctx.respond(f"❌ Error: {e}")"""

old_remove = """class DbRemoveSpecialRole:
    steam_id = crescent.option(str, "Steam ID del jugador")
    rol_especial = crescent.option(hikari.Role, "Rol especial a remover")

    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer()
        try:
            await plugin.model.api.remove_special_role(self.steam_id, str(self.rol_especial.id))
            await ctx.respond(f"✅ Rol especial <@&{self.rol_especial.id}> removido del jugador {self.steam_id}.")
        except Exception as e:
            await ctx.respond(f"❌ Error: {e}")"""

new_remove = """class DbRemoveSpecialRole:
    usuario = crescent.option(hikari.User, "Usuario de Discord") # type: ignore
    rol_especial = crescent.option(str, "Rol especial a remover de BD", choices=[("ADMIN", "ADMIN"), ("OWNER", "OWNER"), ("VIP", "VIP")]) # type: ignore

    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer()
        try:
            player_info = await plugin.model.api.get_player_by_discord(str(self.usuario.id))
            if not player_info:
                await ctx.respond(f"❌ El usuario {self.usuario.mention} no está vinculado.")
                return
            steam_id = player_info.get("steam_id")
            await plugin.model.api.remove_special_role(steam_id, self.rol_especial)
            await ctx.respond(f"✅ Rol especial `{self.rol_especial}` removido del jugador {self.usuario.mention} (SteamID: {steam_id}).")
        except Exception as e:
            await ctx.respond(f"❌ Error: {e}")"""


def replace_block(content, class_name, new_block):
    start = content.find(f"class {class_name}:")
    end = content.find("@plugin.include", start)
    if end == -1: end = len(content)
    return content[:start] + new_block + "\n\n" + content[end:]

content = replace_block(content, "DbAddSpecialRole", new_add)
content = replace_block(content, "DbRemoveSpecialRole", new_remove)

with open("apps/discord_bot/src/plugins/database.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Updated database.py")
