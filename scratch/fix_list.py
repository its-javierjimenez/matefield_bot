with open("d:/proyectos_dev/matefield_bot/apps/discord_bot/src/plugins/config.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

start_idx = -1
for i, line in enumerate(lines):
    if "class ListVipRoles:" in line:
        start_idx = i - 4 # Include decorators
        break

end_idx = -1
for i, line in enumerate(lines):
    if i > start_idx and "class MapMembershipRole:" in line:
        end_idx = i - 4 # Before decorators of MapMembershipRole
        break

if start_idx != -1 and end_idx != -1:
    new_code = """@plugin.include
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
            
        mentions_text = "\\n".join(mentions)
        await ctx.respond(f"📋 **Roles VIP Configurados:**\\n{mentions_text}")

"""
    lines[start_idx:end_idx] = [new_code]
    with open("d:/proyectos_dev/matefield_bot/apps/discord_bot/src/plugins/config.py", "w", encoding="utf-8") as f:
        f.writelines(lines)
    print("Success replacing!")
else:
    print(f"Failed to find indices: start={start_idx} end={end_idx}")
