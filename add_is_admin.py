import re

with open('d:/proyectos_dev/server_rcon_automation/apps/discord_bot/src/hooks.py', 'r', encoding='utf-8') as f:
    content = f.read()

new_func = '''
async def check_is_admin(ctx: crescent.Context) -> bool:
    if not ctx.member:
        return False
        
    if isinstance(ctx.member, hikari.InteractionMember) and (ctx.member.permissions & hikari.Permissions.ADMINISTRATOR) == hikari.Permissions.ADMINISTRATOR:
        return True
        
    admin_role_str = await ctx.client.model.api.get_bot_config("ADMIN_ROLE_ID")
    admin_role_id = int(admin_role_str) if admin_role_str else 0
    return admin_role_id in ctx.member.role_ids
'''

content = content + new_func

with open('d:/proyectos_dev/server_rcon_automation/apps/discord_bot/src/hooks.py', 'w', encoding='utf-8') as f:
    f.write(content)
