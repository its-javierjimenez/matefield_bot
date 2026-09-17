with open("d:/proyectos_dev/matefield_bot/apps/discord_bot/src/plugins/account.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

# find SetWelcomeMessage
start_idx = -1
for i, line in enumerate(lines):
    if "class SetWelcomeMessage:" in line:
        start_idx = i - 3
        break

# find Profile class which comes after on_button_click
end_idx = -1
for i, line in enumerate(lines):
    if i > start_idx and "class Profile:" in line:
        end_idx = i - 4
        break

if start_idx != -1 and end_idx != -1:
    new_code = """@plugin.include
@crescent.hook(admin_only)
@player_group.child
@crescent.command(name="welcome_message_set", description="Establece un mensaje de bienvenida personalizado (VIP/ADMIN)")
class SetWelcomeMessage:
    message = crescent.option(str, "El mensaje que se mostrará cuando entres al servidor")
    steam_id: str | None = crescent.option(str, "Steam ID del jugador a editar (opcional)", default=None)
    usuario: hikari.User | None = crescent.option(hikari.User, "Usuario de Discord a editar (opcional)", default=None)

    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer(ephemeral=False)
        
        if len(self.message) > 60:
            await ctx.respond("❌ El mensaje no puede tener más de 60 caracteres.")
            return
            
        target_steam = self.steam_id
        if self.usuario:
            db_player = await plugin.model.api.get_player_by_discord(str(self.usuario.id))
            if not db_player:
                await ctx.respond(f"❌ El usuario {self.usuario.mention} no tiene una cuenta vinculada.")
                return
            target_steam = db_player.get("steam_id")
            
        if not target_steam:
            discord_id = str(ctx.user.id)
            user_data = await plugin.model.api.get_player_by_discord(discord_id)
            if not user_data or not user_data.get("steam_id"):
                await ctx.respond("❌ Debes vincular tu cuenta de Steam primero usando `/player link` o especificar a quién editar.")
                return
            target_steam = user_data["steam_id"]
            
        steam_data = await plugin.model.api.get_player_by_steam(target_steam)
        active_role = steam_data.get("active_role") if steam_data else None
        
        if not active_role:
            await ctx.respond(f"❌ El jugador no tiene una membresía VIP o ADMIN activa. No se puede establecer el mensaje.")
            return
            
        await plugin.model.api.set_welcome_message(target_steam, self.message)
        await ctx.respond(f"✅ Mensaje de bienvenida establecido exitosamente para `{target_steam}`:\n> {self.message}")

"""
    lines[start_idx:end_idx] = [new_code]
    with open("d:/proyectos_dev/matefield_bot/apps/discord_bot/src/plugins/account.py", "w", encoding="utf-8") as f:
        f.writelines(lines)
    print("Success replacing!")
else:
    print(f"Failed to find indices: start={start_idx} end={end_idx}")
