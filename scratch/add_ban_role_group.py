with open("apps/discord_bot/src/groups.py", "r", encoding="utf-8") as f:
    content = f.read()

if "ban_role_group" not in content:
    content += '\nban_role_group = crescent.Group("ban_role", "Mapeo de roles a baneos", hooks=[admin_only])'
    with open("apps/discord_bot/src/groups.py", "w", encoding="utf-8") as f:
        f.write(content)
        print("Updated groups.py")
