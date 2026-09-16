import os

files = {
    "d:/proyectos_dev/matefield_bot/apps/discord_bot/src/plugins/admin.py": 
        "from src.groups import reserved_group, server_group, quota_group, hacker_group, ban_group",
    "d:/proyectos_dev/matefield_bot/apps/discord_bot/src/plugins/database.py":
        "from src.groups import leaderboard_group, membership_group, player_group, server_group, special_role_group",
    "d:/proyectos_dev/matefield_bot/apps/discord_bot/src/plugins/match.py":
        "from src.groups import match_group, server_group",
}

for fpath, import_line in files.items():
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()
    
    if import_line in content:
        print(f"{os.path.basename(fpath)}: already has import, skipping")
        continue
    
    # Add import after plugin = ... line
    marker = "plugin = crescent.Plugin"
    idx = content.find(marker)
    if idx < 0:
        print(f"{os.path.basename(fpath)}: marker not found!")
        continue
    
    # Find end of that line
    end_of_line = content.find("\n", idx)
    content = content[:end_of_line+1] + import_line + "\n" + content[end_of_line+1:]
    
    # Remove local group definitions that conflict with imports
    # match.py has a local match_group
    if "match.py" in fpath:
        content = content.replace('match_group = crescent.Group("match", "Comandos de Partida en Vivo", hooks=[admin_only])\n', '')
    
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"{os.path.basename(fpath)}: fixed")
