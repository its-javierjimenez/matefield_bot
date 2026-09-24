import crescent
from src.hooks import admin_only

membership_group = crescent.Group("membership", "Administración de membresías", hooks=[admin_only])
special_role_group = crescent.Group("special_role", "Roles especiales", hooks=[admin_only])
player_group = crescent.Group("player", "Comandos de jugadores")
server_group = crescent.Group("server", "Comandos de servidor")
config_group = crescent.Group("config", "Configuración del bot", hooks=[admin_only])
vip_role_group = crescent.Group("vip_role", "Roles VIP", hooks=[admin_only])
roles_group = crescent.Group("roles", "Configuracion de Roles DDD", hooks=[admin_only])
whitelist_group = crescent.Group("whitelist", "Whitelist del bot", hooks=[admin_only])
ban_group = crescent.Group("ban", "Baneos", hooks=[admin_only])
quota_group = crescent.Group("quota", "Cupos", hooks=[admin_only])
hacker_group = crescent.Group("hacker", "Herramientas anti-hacks", hooks=[admin_only])
reserved_group = crescent.Group("reserved_slots", "Slots reservados", hooks=[admin_only])
match_group = crescent.Group("match", "Partida en vivo")
leaderboard_group = crescent.Group("leaderboard", "Top jugadores")

ban_role_group = crescent.Group("ban_role", "Mapeo de roles a baneos", hooks=[admin_only])
rcon_group = crescent.Group("rcon", "Gestión de servidores RCON", hooks=[admin_only])
membership_type_group = crescent.Group("membership_type", "Gestión de paquetes y tipos de membresía", hooks=[admin_only])