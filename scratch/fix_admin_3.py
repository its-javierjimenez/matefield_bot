import re

with open("d:/proyectos_dev/matefield_bot/apps/discord_bot/src/plugins/admin.py", "r", encoding="utf-8") as f:
    content = f.read()

# fetch_member requires the guild_id to not be None
def repl(m):
    return "if not ctx.guild_id:\n                        return\n                    " + m.group(0)

# We want to replace lines like `member = plugin.app.cache.get_member(ctx.guild_id, discord_id) or await ctx.app.rest.fetch_member(ctx.guild_id, discord_id)`
content = re.sub(r'member = plugin\.app\.cache\.get_member\(ctx\.guild_id, .*? fetch_member\(ctx\.guild_id, .*?\)', repl, content)

with open("d:/proyectos_dev/matefield_bot/apps/discord_bot/src/plugins/admin.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Fixed guild_id in admin.py")
