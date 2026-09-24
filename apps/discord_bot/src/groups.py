import crescent
from src.hooks import admin_only

membership_group = crescent.Group("membership", "Administración de membresías", hooks=[admin_only])
special_role_group = crescent.Group("special_role", "Roles especiales", hooks=[admin_only])
player_group = crescent.Group("player", "Comandos de jugadores")
server_group = crescent.Group("server", "Comandos de servidor")
config_group = crescent.Group("config", "Configuración del bot", hooks=[admin_only])
vip_role_group = crescent.Group("vip_role", "Roles VIP", hooks=[admin_only])
role_map_group = crescent.Group("role_map", "Mapeos de roles", hooks=[admin_only])
whitelist_group = crescent.Group("whitelist", "Whitelist del bot", hooks=[admin_only])
ban_group = crescent.Group("ban", "Baneos", hooks=[admin_only])
quota_group = crescent.Group("quota", "Cupos", hooks=[admin_only])
hacker_group = crescent.Group("hacker", "Herramientas anti-hacks", hooks=[admin_only])
reserved_group = crescent.Group("reserved_slots", "Slots reservados", hooks=[admin_only])
match_group = crescent.Group("match", "Partida en vivo")
leaderboard_group = crescent.Group("leaderboard", "Top jugadores")

ban_role_group = crescent.Group("ban_role", "Mapeo de roles a baneos", hooks=[admin_only])
db_group = crescent.Group("db", "Comandos de base de datos y backups", hooks=[admin_only])
role_group = crescent.Group("role", "Configuración de roles", hooks=[admin_only])