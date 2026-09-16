with open("apps/discord_bot/src/plugins/admin.py", "r", encoding="utf-8") as f:
    content = f.read()

import re

# We will modify the Crescent decorators

# 1. Ban group is already there for list, let's use it for add/remove
content = content.replace('@crescent.command(name="ban", description="Banea a un jugador por Steam ID y sincroniza con RCON")', '@ban_group.child\n@crescent.command(name="add", description="Banea a un jugador por Steam ID y sincroniza con RCON")')
content = content.replace('@crescent.command(name="unban", description="Desbanea a un jugador por Steam ID y sincroniza con RCON")', '@ban_group.child\n@crescent.command(name="remove", description="Desbanea a un jugador por Steam ID y sincroniza con RCON")')

# Move ban_group definition to the top so it can be used by BanPlayer and UnbanPlayer
ban_group_def = 'ban_group = crescent.Group("ban", description="Administración de baneos", hooks=[admin_only])\n'
content = content.replace('# Grupo Bans\n' + ban_group_def, '')
content = content.replace('@crescent.command(name="add", description="Banea a un jugador por Steam ID y sincroniza con RCON")', ban_group_def + '\n@crescent.command(name="add", description="Banea a un jugador por Steam ID y sincroniza con RCON")')

# 2. Quota Group
quota_group_def = 'quota_group = crescent.Group("quota", description="Administración de cupos", hooks=[admin_only])\n'
content = content.replace('@crescent.command(name="quotas", description="Revisar la ocupación de cupos de las membresías")', quota_group_def + '\n@quota_group.child\n@crescent.command(name="list", description="Revisar la ocupación de cupos de las membresías")')
content = content.replace('@crescent.command(name="set_quota", description="Configurar el límite de un tipo de membresía")', '@quota_group.child\n@crescent.command(name="set", description="Configurar el límite de un tipo de membresía")')

# 3. Server Group (for server_set_max_reserved, server_announce)
server_group_def = 'server_group = crescent.Group("server", description="Administración del servidor", hooks=[admin_only])\n'
content = content.replace('@crescent.command(name="set_max_reserved", description="Modifica el límite máximo de slots reservados (ServerSettings.ini)")', server_group_def + '\n@server_group.child\n@crescent.command(name="set_max_reserved", description="Modifica el límite máximo de slots reservados (ServerSettings.ini)")')
content = content.replace('@crescent.command(name="announce", description="Envía un anuncio al servidor RCON")', '@server_group.child\n@crescent.command(name="announce", description="Envía un anuncio al servidor RCON")')

# 4. Hacker Group
hacker_group_def = 'hacker_group = crescent.Group("hacker", description="Herramientas contra hackers", hooks=[admin_only])\n'
content = content.replace('@crescent.command(name="monitor_hacker", description="Monitorea a un jugador para detectar hacks usando KPM")', hacker_group_def + '\n@hacker_group.child\n@crescent.command(name="monitor", description="Monitorea a un jugador para detectar hacks usando KPM")')

with open("apps/discord_bot/src/plugins/admin.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Refactored admin.py commands")
