import httpx
import logging

# We will just append the command text to admin.py
code = '''
@plugin.include
@crescent.hook(admin_only)
@crescent.command(name="compensar_todos", description="Extiende todas las membresías activas por la cantidad de días indicados")
class CompensarTodos:
    dias = crescent.option(int, "Cantidad de días a extender")
    
    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer(ephemeral=True)
        try:
            res = await plugin.model.api.compensate_memberships(self.dias)
            msg = res.get("message", "Compensación completada.")
            await ctx.respond(f"✅ {msg}")
        except Exception as e:
            await ctx.respond(f"❌ Error al compensar: {e}")

@plugin.include
@crescent.hook(admin_only)
@crescent.command(name="extender_membresia", description="Extiende una membresía individual por ID")
class ExtenderMembresia:
    membership_id = crescent.option(int, "ID numérico de la membresía")
    dias = crescent.option(int, "Cantidad de días extra")
    
    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer(ephemeral=True)
        try:
            await plugin.model.api.edit_membership(membership_id=self.membership_id, add_days=self.dias)
            await ctx.respond(f"✅ Membresía #{self.membership_id} extendida por {self.dias} días exitosamente.")
        except Exception as e:
            await ctx.respond(f"❌ Error al extender membresía: {e}")
'''
with open('d:/proyectos_dev/server_rcon_automation/apps/discord_bot/src/plugins/admin.py', 'a', encoding='utf-8') as f:
    f.write(code)
print('Done!')
