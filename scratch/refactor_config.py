with open("apps/discord_bot/src/plugins/config.py", "r", encoding="utf-8") as f:
    content = f.read()

import re

new_groups = """
config_group = crescent.Group("config", "Configuraciones del bot", hooks=[admin_only])
vip_role_group = crescent.Group("vip_role", "Configuración de roles VIP", hooks=[admin_only])
role_map_group = crescent.Group("role_map", "Mapeo de membresías a roles", hooks=[admin_only])
whitelist_group = crescent.Group("whitelist", "Excepciones de sincronización", hooks=[admin_only])
"""
content = re.sub(r'plugin = crescent.Plugin\(\)\n', 'plugin = crescent.Plugin()\n' + new_groups, content)

# Replace decorators
# set_announcement_channel -> config announcement_channel
content = content.replace('@crescent.command(name="set_announcement_channel"', '@config_group.child\n@crescent.command(name="announcement_channel"')
# set_admin_role -> config admin_role
content = content.replace('@crescent.command(name="set_admin_role"', '@config_group.child\n@crescent.command(name="admin_role"')
# set_match_channel -> config match_channel
content = content.replace('@crescent.command(name="set_match_channel"', '@config_group.child\n@crescent.command(name="match_channel"')
# view_all -> config list
content = content.replace('@crescent.command(name="view_all"', '@config_group.child\n@crescent.command(name="list"')

# add_vip_role -> vip_role add
content = content.replace('@crescent.command(name="add_vip_role"', '@vip_role_group.child\n@crescent.command(name="add"')
# remove_vip_role -> vip_role remove
content = content.replace('@crescent.command(name="remove_vip_role"', '@vip_role_group.child\n@crescent.command(name="remove"')
# vip_roles -> vip_role list
content = content.replace('@crescent.command(name="vip_roles"', '@vip_role_group.child\n@crescent.command(name="list"')

# map_role -> role_map add
content = content.replace('@crescent.command(name="map_role"', '@role_map_group.child\n@crescent.command(name="add"')
# unmap_role -> role_map remove
content = content.replace('@crescent.command(name="unmap_role"', '@role_map_group.child\n@crescent.command(name="remove"')

# add_whitelist -> whitelist add
content = content.replace('@crescent.command(name="add_whitelist"', '@whitelist_group.child\n@crescent.command(name="add"')
# remove_whitelist -> whitelist remove
content = content.replace('@crescent.command(name="remove_whitelist"', '@whitelist_group.child\n@crescent.command(name="remove"')
# whitelist -> whitelist list
content = content.replace('@crescent.command(name="whitelist"', '@whitelist_group.child\n@crescent.command(name="list"')

with open("apps/discord_bot/src/plugins/config.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Refactored config.py commands")
