import re

# router.py
with open("d:/proyectos_dev/matefield_bot/apps/api_rcon/src/modules/v1/router.py", "r", encoding="utf-8") as f:
    router_code = f.read()
if "from sqlalchemy import text" not in router_code:
    router_code = router_code.replace("from sqlalchemy import func, select", "from sqlalchemy import func, select, text")
with open("d:/proyectos_dev/matefield_bot/apps/api_rcon/src/modules/v1/router.py", "w", encoding="utf-8") as f:
    f.write(router_code)

# admin.py
with open("d:/proyectos_dev/matefield_bot/apps/discord_bot/src/plugins/admin.py", "r", encoding="utf-8") as f:
    admin_code = f.read()
admin_code = admin_code.replace("get_db_bans(steam_id)", "get_db_bans(str(steam_id))")
admin_code = admin_code.replace("get_db_bans(self.steam_id)", "get_db_bans(str(self.steam_id))")
with open("d:/proyectos_dev/matefield_bot/apps/discord_bot/src/plugins/admin.py", "w", encoding="utf-8") as f:
    f.write(admin_code)

# database.py
with open("d:/proyectos_dev/matefield_bot/apps/discord_bot/src/plugins/database.py", "r", encoding="utf-8") as f:
    db_code = f.read()
db_code = db_code.replace(" # type: ignore", "")
with open("d:/proyectos_dev/matefield_bot/apps/discord_bot/src/plugins/database.py", "w", encoding="utf-8") as f:
    f.write(db_code)
print("Applied final fixes")
