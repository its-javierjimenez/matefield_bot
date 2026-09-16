@plugin.include
@crescent.hook(admin_only)
@crescent.command(name="sync_memberships", description="[DEV] Otorga membresías a usuarios vinculados basándose en sus roles de Discord")
class ForceSyncRolesToMemberships:
    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer()
        configs = await plugin.model.api.get_bot_configs()
        role_maps = {} # role_id_str -> db_type
        
        for key, value in configs.items():
            if key.startswith("ROLE_MAP_"):
                db_type = key.replace("ROLE_MAP_", "")
                role_maps[value] = db_type
                
        if not role_maps:
            await ctx.respond("ℹ️ No hay mapeos de roles configurados en /config map_membership_role.")
            return
            
        # Get all linked players (up to 1000 for testing)
        res = await plugin.model.api.get_paginated_players(page=1, limit=1000, linked="all")
        players = res.get("players", [])
        
        if not players:
            await ctx.respond("ℹ️ No hay jugadores vinculados en la base de datos.")
            return
            
        imported = 0
        guild_id = ctx.guild_id
        if not guild_id:
            await ctx.respond("❌ Este comando debe usarse en un servidor.")
            return
            
        skipped = 0
        for p in players:
            discord_id = p.get("discord_id")
            steam_id = p.get("steam_id")
            if not discord_id or not steam_id:
                logger.info(f"[ForceSync] Saltando jugador sin discord_id o steam_id: {p}")
                continue
                
            try:
                member = await plugin.app.rest.fetch_member(guild_id, int(discord_id))
            except Exception as e:
                logger.info(f"[ForceSync] No se pudo obtener member para discord_id {discord_id}: {e}")
                continue
                
            member_role_ids = [str(r) for r in member.role_ids]
            logger.info(f"[ForceSync] Jugador {discord_id} tiene roles: {member_role_ids}")
            
            for role_id_str, db_type in role_maps.items():
                if role_id_str in member_role_ids:
                    try:
                        # Call add_membership without days to use default config
                        await plugin.model.api.add_membership(steam_id, db_type)
                        logger.info(f"[ForceSync] Otorgada membresía {db_type} a steam_id {steam_id}")
                        imported += 1
                    except Exception as e:
                        if "Membership already active" in str(e):
                            skipped += 1
                            logger.info(f"[ForceSync] Omitido: {steam_id} ya tiene membresía activa.")
                        else:
                            logger.error(f"[ForceSync] Falló add_membership para {steam_id}: {e}")
                        
        msg = f"✅ Sincronización completada. Se otorgaron {imported} membresías nuevas."
        if skipped > 0:
            msg += f"\n⚠️ Se omitieron {skipped} membresías porque los usuarios ya la tenían activa."
            
        await ctx.respond(msg)

import time


@plugin.include
@crescent.hook(admin_only)
@crescent.command(name="compensar_todos", description="Extiende todas las membresías activas por la cantidad de días indicados")
class CompensarTodos:
    dias = crescent.option(int, "Cantidad de días a extender")
    
    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer()
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
        await ctx.defer()
        try:
            await plugin.model.api.edit_membership(membership_id=self.membership_id, add_days=self.dias)
            await ctx.respond(f"✅ Membresía #{self.membership_id} extendida por {self.dias} días exitosamente.")
        except Exception as e:
            await ctx.respond(f"❌ Error al extender membresía: {e}")


