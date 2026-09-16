with open("apps/discord_bot/src/plugins/account.py", "r", encoding="utf-8") as f:
    content = f.read()

old_block = """class LinkAccount:
    steam_id = crescent.option(str, "Tu Steam ID de 64 bits")

    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer(ephemeral=True)
        
        discord_id = str(ctx.user.id)
        await plugin.model.api.link_account(discord_id, self.steam_id)
        
        await ctx.respond(f"✅ Cuenta vinculada exitosamente con el Steam ID `{self.steam_id}`")"""

new_block = """class LinkAccount:
    steam_id = crescent.option(str, "Tu Steam ID de 64 bits")
    usuario = crescent.option(hikari.User, "Usuario a vincular (Solo admin)", default=None) # type: ignore

    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer(ephemeral=True)
        
        target_id = str(ctx.user.id)
        
        if self.usuario:
            is_admin = await check_is_admin(ctx)
            if not is_admin:
                await ctx.respond("❌ Solo los administradores pueden vincular a otros usuarios.")
                return
            target_id = str(self.usuario.id)
            
        try:
            await plugin.model.api.link_account(target_id, self.steam_id)
            
            if self.usuario:
                await ctx.respond(f"✅ Has vinculado a {self.usuario.mention} con el Steam ID `{self.steam_id}`")
            else:
                await ctx.respond(f"✅ Tu cuenta ha sido vinculada exitosamente con el Steam ID `{self.steam_id}`")
        except Exception as e:
            await ctx.respond(f"❌ Error al vincular: {e}")"""

# find class LinkAccount:
start_idx = content.find('class LinkAccount:')
end_idx = content.find('@plugin.include', start_idx)

if start_idx != -1 and end_idx != -1:
    new_content = content[:start_idx] + new_block + "\n\n" + content[end_idx:]
    with open("apps/discord_bot/src/plugins/account.py", "w", encoding="utf-8") as f:
        f.write(new_content)
    print("Success: account.py modified")
else:
    print("Error finding block")
