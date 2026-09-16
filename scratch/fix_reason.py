with open("d:/proyectos_dev/matefield_bot/apps/api_rcon/src/modules/v1/router.py", "r", encoding="utf-8") as f:
    r_code = f.read()

r_code = r_code.replace('reason="Synced from RCON"', 'reason=""')

with open("d:/proyectos_dev/matefield_bot/apps/api_rcon/src/modules/v1/router.py", "w", encoding="utf-8") as f:
    f.write(r_code)

print("Updated reason for synced bans")
