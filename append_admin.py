import httpx
import logging

# We will just append the command text to admin.py
code = '''
@plugin.include
@crescent.hook(admin_only)
@crescent.command(name="ban", description="Banea a un jugador por Steam ID y sincroniza con RCON")
class BanPlayer:
    steam_id = crescent.option(str, "Steam ID a banear")
    reason = crescent.option(str, "Razón del ban", default="No especificado")
    
    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer(ephemeral=True)
        try:
            url = f"{plugin.model.api.base_url}/players/{self.steam_id}/ban"
            headers = {"X-API-Key": plugin.model.api.api_key}
            payload = {"reason": self.reason}
            
            async with httpx.AsyncClient() as client:
                res = await client.post(url, headers=headers, json=payload)
                
            if res.status_code == 200:
                await ctx.respond(f"✅ Jugador {self.steam_id} ha sido baneado permanentemente en la base de datos y RCON. Razón: {self.reason}")
            else:
                await ctx.respond(f"❌ Error al banear: {res.text}")
        except Exception as e:
            await ctx.respond(f"❌ Error interno: {e}")

@plugin.include
@crescent.hook(admin_only)
@crescent.command(name="unban", description="Desbanea a un jugador por Steam ID y sincroniza con RCON")
class UnbanPlayer:
    steam_id = crescent.option(str, "Steam ID a desbanear")
    
    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer(ephemeral=True)
        try:
            url = f"{plugin.model.api.base_url}/players/{self.steam_id}/unban"
            headers = {"X-API-Key": plugin.model.api.api_key}
            
            async with httpx.AsyncClient() as client:
                res = await client.post(url, headers=headers)
                
            if res.status_code == 200:
                await ctx.respond(f"✅ Jugador {self.steam_id} ha sido desbaneado y sincronizado con RCON.")
            else:
                await ctx.respond(f"❌ Error al desbanear: {res.text}")
        except Exception as e:
            await ctx.respond(f"❌ Error interno: {e}")
'''
with open('d:/proyectos_dev/server_rcon_automation/apps/discord_bot/src/plugins/admin.py', 'a', encoding='utf-8') as f:
    f.write(code)
print('Done!')
