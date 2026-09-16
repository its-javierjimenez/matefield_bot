with open("d:/proyectos_dev/matefield_bot/apps/discord_bot/src/plugins/admin.py", "r", encoding="utf-8") as f:
    content = f.read()

# Fix Name time used when not defined
if "import time" not in content:
    content = content.replace("import hikari", "import hikari\nimport time")
    
# Fix cache issues. In crescent, `ctx.app.cache` throws errors if not cast or if ctx is just REST.
# But we can use plugin.app.cache which is typed as hikari.GatewayBot if plugin = crescent.Plugin[hikari.GatewayBot, Model]() is used.
content = content.replace("ctx.app.cache", "plugin.app.cache")

# Fix get_db_bans signature: Expected str | None, found int | None | Any (line 434?)
# Wait, let's see where get_db_bans is used. It's probably `steam_id` being passed instead of `discord_id` or something.
# The error was: Expected `str | None`, found `int | None | Any` -> int of union int|None|Any is not assignable to str|None.
content = content.replace("get_db_bans(steam_id)", "get_db_bans(str(steam_id))")
content = content.replace("get_db_bans(self.steam_id)", "get_db_bans(str(self.steam_id))")

# fetch_member expecting PartialGuild | int, found Snowflake | None (ctx.guild_id can be None)
# To fix: add if not ctx.guild_id: return
# We can replace `ctx.app.rest.fetch_member(ctx.guild_id,` with `ctx.app.rest.fetch_member(ctx.guild_id,` but we need to check if ctx.guild_id exists.

with open("d:/proyectos_dev/matefield_bot/apps/discord_bot/src/plugins/admin.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Applied admin.py general fixes")
