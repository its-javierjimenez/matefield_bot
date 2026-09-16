import re

# router.py
with open("d:/proyectos_dev/matefield_bot/apps/api_rcon/src/modules/v1/router.py", "r", encoding="utf-8") as f:
    router_code = f.read()
if "from sqlalchemy import text" not in router_code:
    router_code = router_code.replace("from sqlalchemy import func, select", "from sqlalchemy import func, select, text")
router_code = router_code.replace("func.count(MatchPlayerStats.steam_id).label(", "func.count(text('1')).label(")
with open("d:/proyectos_dev/matefield_bot/apps/api_rcon/src/modules/v1/router.py", "w", encoding="utf-8") as f:
    f.write(router_code)

# admin.py
with open("d:/proyectos_dev/matefield_bot/apps/discord_bot/src/plugins/admin.py", "r", encoding="utf-8") as f:
    admin_code = f.read()

# fetch_member
def repl_member(m):
    return """guild_id = ctx.guild_id
                    if not guild_id:
                        return
                    member = plugin.app.cache.get_member(guild_id, discord_id) or await ctx.app.rest.fetch_member(guild_id, discord_id)"""

admin_code = re.sub(r'if not ctx\.guild_id:\n\s*return\n\s*member = plugin\.app\.cache\.get_member\(ctx\.guild_id, .*? fetch_member\(ctx\.guild_id, .*?\)', repl_member, admin_code)
admin_code = admin_code.replace("get_db_bans(steam_id)", "get_db_bans(str(steam_id))")

with open("d:/proyectos_dev/matefield_bot/apps/discord_bot/src/plugins/admin.py", "w", encoding="utf-8") as f:
    f.write(admin_code)

# database.py
with open("d:/proyectos_dev/matefield_bot/apps/discord_bot/src/plugins/database.py", "r", encoding="utf-8") as f:
    db_code = f.read()

# Add # type: ignore to crescent.option assignments that are complaining
lines = db_code.split("\n")
for i, line in enumerate(lines):
    if "crescent.option" in line and "# type: ignore" not in line:
        lines[i] = line + " # type: ignore"

db_code = "\n".join(lines)
with open("d:/proyectos_dev/matefield_bot/apps/discord_bot/src/plugins/database.py", "w", encoding="utf-8") as f:
    f.write(db_code)
print("Applied type fixes")
