with open("d:/proyectos_dev/matefield_bot/apps/api_rcon/src/modules/v1/router.py", "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace("VIP\\\" \"\"\"", "VIP\"")
content = content.replace("VIP\\\" \"", "VIP\"")
content = content.replace("VIP\\\"\"", "VIP\"")

with open("d:/proyectos_dev/matefield_bot/apps/api_rcon/src/modules/v1/router.py", "w", encoding="utf-8") as f:
    f.write(content)
