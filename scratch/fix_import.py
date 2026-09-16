with open("d:/proyectos_dev/matefield_bot/apps/discord_bot/src/plugins/config.py", "r", encoding="utf-8") as f:
    content = f.read()

old = "from src.hooks import admin_only\n\nplugin"
new = "from src.hooks import admin_only\nfrom src.groups import config_group, vip_role_group, role_map_group, whitelist_group, ban_role_group\n\nplugin"

if old in content:
    content = content.replace(old, new)
    with open("d:/proyectos_dev/matefield_bot/apps/discord_bot/src/plugins/config.py", "w", encoding="utf-8") as f:
        f.write(content)
    print("Fixed")
else:
    print("Pattern not found!")
    # Debug
    idx = content.find("from src.hooks")
    print(repr(content[idx:idx+100]))
