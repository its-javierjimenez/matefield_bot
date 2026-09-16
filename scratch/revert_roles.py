with open("apps/discord_bot/src/plugins/database.py", "r", encoding="utf-8") as f:
    content = f.read()

# Fix add_special_role: keep @User but revert to hikari.Role
old_add = '''class DbAddSpecialRole:
    usuario = crescent.option(hikari.User, "Usuario de Discord") # type: ignore
    rol_especial = crescent.option(str, "Rol especial a asignar en BD", choices=[("ADMIN", "ADMIN"), ("OWNER", "OWNER"), ("VIP", "VIP")]) # type: ignore

    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer()
        try:
            player_info = await plugin.model.api.get_player_by_discord(str(self.usuario.id))
            if not player_info:
                await ctx.respond(f"\u274c El usuario {self.usuario.mention} no est\u00e1 vinculado.")
                return
            steam_id = player_info.get("steam_id")
            await plugin.model.api.add_special_role(steam_id, self.rol_especial)
            await ctx.respond(f"\u2705 Rol especial `{self.rol_especial}` a\u00f1adido al jugador {self.usuario.mention} (SteamID: {steam_id}).")
        except Exception as e:
            await ctx.respond(f"\u274c Error: {e}")'''

new_add = '''class DbAddSpecialRole:
    usuario = crescent.option(hikari.User, "Usuario de Discord") # type: ignore
    rol_especial = crescent.option(hikari.Role, "Rol especial a asignar") # type: ignore

    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer()
        try:
            player_info = await plugin.model.api.get_player_by_discord(str(self.usuario.id))
            if not player_info:
                await ctx.respond(f"\u274c El usuario {self.usuario.mention} no est\u00e1 vinculado.")
                return
            steam_id = player_info.get("steam_id")
            await plugin.model.api.add_special_role(steam_id, str(self.rol_especial.id))
            await ctx.respond(f"\u2705 Rol especial <@&{self.rol_especial.id}> a\u00f1adido al jugador {self.usuario.mention} (`{steam_id}`).")
        except Exception as e:
            await ctx.respond(f"\u274c Error: {e}")'''

# Fix remove_special_role: keep @User but revert to hikari.Role
old_remove = '''class DbRemoveSpecialRole:
    usuario = crescent.option(hikari.User, "Usuario de Discord") # type: ignore
    rol_especial = crescent.option(str, "Rol especial a remover de BD", choices=[("ADMIN", "ADMIN"), ("OWNER", "OWNER"), ("VIP", "VIP")]) # type: ignore

    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer()
        try:
            player_info = await plugin.model.api.get_player_by_discord(str(self.usuario.id))
            if not player_info:
                await ctx.respond(f"\u274c El usuario {self.usuario.mention} no est\u00e1 vinculado.")
                return
            steam_id = player_info.get("steam_id")
            await plugin.model.api.remove_special_role(steam_id, self.rol_especial)
            await ctx.respond(f"\u2705 Rol especial `{self.rol_especial}` removido del jugador {self.usuario.mention} (SteamID: {steam_id}).")
        except Exception as e:
            await ctx.respond(f"\u274c Error: {e}")'''

new_remove = '''class DbRemoveSpecialRole:
    usuario = crescent.option(hikari.User, "Usuario de Discord") # type: ignore
    rol_especial = crescent.option(hikari.Role, "Rol especial a remover") # type: ignore

    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer()
        try:
            player_info = await plugin.model.api.get_player_by_discord(str(self.usuario.id))
            if not player_info:
                await ctx.respond(f"\u274c El usuario {self.usuario.mention} no est\u00e1 vinculado.")
                return
            steam_id = player_info.get("steam_id")
            await plugin.model.api.remove_special_role(steam_id, str(self.rol_especial.id))
            await ctx.respond(f"\u2705 Rol especial <@&{self.rol_especial.id}> removido del jugador {self.usuario.mention} (`{steam_id}`).")
        except Exception as e:
            await ctx.respond(f"\u274c Error: {e}")'''

content = content.replace(old_add, new_add)
content = content.replace(old_remove, new_remove)

with open("apps/discord_bot/src/plugins/database.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Reverted to hikari.Role, kept @User")
