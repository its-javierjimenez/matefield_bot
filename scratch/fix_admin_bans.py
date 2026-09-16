with open("d:/proyectos_dev/matefield_bot/apps/discord_bot/src/plugins/admin.py", "r", encoding="utf-8") as f:
    a_code = f.read()

# Replace the wrong str(target_steam) with the correct check
a_code = a_code.replace("data = await plugin.model.api.get_db_bans(str(target_steam))", "data = await plugin.model.api.get_db_bans(str(target_steam) if target_steam else None)")

with open("d:/proyectos_dev/matefield_bot/apps/discord_bot/src/plugins/admin.py", "w", encoding="utf-8") as f:
    f.write(a_code)

print("Fixed str(target_steam) issue in admin.py")
