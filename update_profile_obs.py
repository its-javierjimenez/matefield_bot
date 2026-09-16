import re

with open('d:/proyectos_dev/server_rcon_automation/apps/discord_bot/src/plugins/account.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Add import if missing
if "from src.hooks import" not in content:
    content = "from src.hooks import check_is_admin\n" + content
elif "check_is_admin" not in content:
    content = content.replace("from src.hooks import", "from src.hooks import check_is_admin,")

# Find the spot to insert the observations logic inside Profile.callback
# After: embed.add_field(name="⭐ Rango RCON", value=active_role, inline=False)
insert_logic = '''
        embed.add_field(name="⭐ Rango RCON", value=active_role, inline=False)
        
        # Check permissions for observations
        is_admin = await check_is_admin(ctx)
        is_owner = (target_discord_id == str(ctx.user.id)) if target_discord_id else False
        
        if is_admin or is_owner:
            obs = steam_data.get("observations")
            if obs:
                embed.add_field(name="📝 Observaciones Internas", value=f"`\\n{obs}\\n`", inline=False)
'''

content = content.replace('embed.add_field(name="⭐ Rango RCON", value=active_role, inline=False)', insert_logic)

with open('d:/proyectos_dev/server_rcon_automation/apps/discord_bot/src/plugins/account.py', 'w', encoding='utf-8') as f:
    f.write(content)
