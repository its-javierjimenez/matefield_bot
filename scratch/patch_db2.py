with open("apps/discord_bot/src/plugins/database.py", "r", encoding="utf-8") as f:
    content = f.read()

old_block = """@plugin.include
@crescent.hook(admin_only)
@db_group.child
@crescent.command(name="edit_player", description="Edita información de un jugador")
class DbEditPlayer:
    steam_id: str = crescent.option(str, "Steam ID del jugador a editar")  # type: ignore
    usuario_discord: hikari.User | None = crescent.option(hikari.User, "Nuevo usuario de Discord a enlazar", default=None)  # type: ignore
    mensaje_bienvenida: str | None = crescent.option(str, "Nuevo mensaje de bienvenida personalizado", default=None)  # type: ignore
    observacion: str | None = crescent.option(str, "Añadir/editar nota interna sobre pagos, conducta, etc.", default=None)  # type: ignore

    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer()
        try:
            discord_id = str(self.usuario_discord.id) if self.usuario_discord else None
            await plugin.model.api.edit_player(self.steam_id, discord_id=discord_id, custom_welcome_message=self.mensaje_bienvenida, observations=self.observacion)
            await ctx.respond(f"✅ Jugador {self.steam_id} actualizado exitosamente.")
        except Exception as e:
            await ctx.respond(f"❌ Error: {e}")"""

new_block = """@plugin.include
@crescent.hook(admin_only)
@db_group.child
@crescent.command(name="link_player", description="Vincula un usuario de Discord a un Steam ID (Admin)")
class DbLinkPlayer:
    usuario_discord = crescent.option(hikari.User, "Usuario de Discord a vincular") # type: ignore
    steam_id = crescent.option(str, "Steam ID del jugador") # type: ignore
    
    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer()
        try:
            await plugin.model.api.link_account(str(self.usuario_discord.id), self.steam_id)
            await ctx.respond(f"✅ Usuario {self.usuario_discord.mention} vinculado al Steam ID `{self.steam_id}` exitosamente.")
        except Exception as e:
            await ctx.respond(f"❌ Error al vincular: {e}")

@plugin.include
@crescent.hook(admin_only)
@db_group.child
@crescent.command(name="edit_player", description="Edita información de un jugador (debe estar vinculado)")
class DbEditPlayer:
    usuario_discord = crescent.option(hikari.User, "Usuario de Discord (jugador vinculado)") # type: ignore
    mensaje_bienvenida = crescent.option(str, "Nuevo mensaje de bienvenida personalizado", default=None) # type: ignore
    observacion = crescent.option(str, "Añadir/editar nota interna sobre pagos, conducta, etc.", default=None) # type: ignore

    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer()
        try:
            player_info = await plugin.model.api.get_player_by_discord(str(self.usuario_discord.id))
            if not player_info:
                await ctx.respond(f"❌ El usuario {self.usuario_discord.mention} no está vinculado a ningún Steam ID. Usa `/db link_player` primero.")
                return
                
            steam_id = player_info.get("steam_id")
            
            await plugin.model.api.edit_player(
                steam_id, 
                custom_welcome_message=self.mensaje_bienvenida, 
                observations=self.observacion
            )
            await ctx.respond(f"✅ Jugador `{steam_id}` ({self.usuario_discord.mention}) actualizado exitosamente.")
        except Exception as e:
            await ctx.respond(f"❌ Error: {e}")"""

# Because of encoding issues with emojis in powershell, we will use regex to find the block
import re

start_idx = content.find('class DbEditPlayer:')
if start_idx != -1:
    # Go back to @plugin.include
    start_idx = content.rfind('@plugin.include', 0, start_idx)
    end_str = 'await ctx.respond(f"\\u274c Error: {e}")' # The emoji might be decoded weirdly
    end_idx = content.find('Error:', start_idx)
    end_idx = content.find('}', end_idx) + 2
    # Wait, just find the next @plugin.include or EOF
    next_plugin_idx = content.find('@plugin.include', end_idx)
    if next_plugin_idx == -1:
        next_plugin_idx = len(content)
        
    old_content_block = content[start_idx:next_plugin_idx]
    
    # We can just replace it
    new_content = content[:start_idx] + new_block + "\n\n" + content[next_plugin_idx:]
    with open("apps/discord_bot/src/plugins/database.py", "w", encoding="utf-8") as f:
        f.write(new_content)
    print("Success: database.py modified")
else:
    print("Error: Could not find class DbEditPlayer")
