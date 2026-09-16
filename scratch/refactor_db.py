with open("apps/discord_bot/src/plugins/database.py", "r", encoding="utf-8") as f:
    content = f.read()

import re

# 1. Remove db_group definition
content = content.replace('db_group = crescent.Group("db", "Comandos de consultas de Base de Datos", hooks=[admin_only])\n', '')

# 2. Add new groups
new_groups = """
membership_group = crescent.Group("membership", "Administración de membresías", hooks=[admin_only])
special_role_group = crescent.Group("special_role", "Administración de roles especiales", hooks=[admin_only])
leaderboard_group = crescent.Group("leaderboard", "Top jugadores")
player_group = crescent.Group("player", "Administración de jugadores", hooks=[admin_only])
server_group = crescent.Group("server", "Estado del servidor", hooks=[admin_only])
"""
content = re.sub(r'plugin = crescent.Plugin\(\)\n', 'plugin = crescent.Plugin()\n' + new_groups, content)

# 3. Replace decorators
# leaderboard
content = content.replace('@db_group.child\n@crescent.command(name="leaderboard"', '@leaderboard_group.child\n@crescent.command(name="list"')
# add_membership -> membership add
content = content.replace('@db_group.child\n@crescent.command(name="add_membership"', '@membership_group.child\n@crescent.command(name="add"')
# players -> player list
content = content.replace('@db_group.child\n@crescent.command(name="players"', '@player_group.child\n@crescent.command(name="list"')
# status -> server status
content = content.replace('@db_group.child\n@crescent.command(name="status"', '@server_group.child\n@crescent.command(name="status"')
# memberships -> membership list
content = content.replace('@db_group.child\n@crescent.command(name="memberships"', '@membership_group.child\n@crescent.command(name="list"')
# edit_membership -> membership edit
content = content.replace('@db_group.child\n@crescent.command(name="edit_membership"', '@membership_group.child\n@crescent.command(name="edit"')
# remove_membership -> membership remove
content = content.replace('@db_group.child\n@crescent.command(name="remove_membership"', '@membership_group.child\n@crescent.command(name="remove"')
# add_special_role -> special_role add
content = content.replace('@db_group.child\n@crescent.command(name="add_special_role"', '@special_role_group.child\n@crescent.command(name="add"')
# remove_special_role -> special_role remove
content = content.replace('@db_group.child\n@crescent.command(name="remove_special_role"', '@special_role_group.child\n@crescent.command(name="remove"')
# edit_player -> player edit
content = content.replace('@db_group.child\n@crescent.command(name="edit_player"', '@player_group.child\n@crescent.command(name="edit"')

# Remove DbReservedSlots entirely (since it's now in admin.py under reserved_slots)
match_res = re.search(r'(@plugin\.include\n@db_group\.child\n@crescent\.command\(name="reserved_slots".*?)(?=@plugin\.include)', content, re.DOTALL)
if match_res:
    content = content.replace(match_res.group(1), "")

with open("apps/discord_bot/src/plugins/database.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Refactored database.py commands")
