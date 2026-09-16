with open("apps/discord_bot/src/plugins/admin.py", "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace('await ctx.defer(ephemeral=True)', 'await ctx.defer()')
content = content.replace('await ctx.respond(current_msg, ephemeral=True)', 'await ctx.respond(current_msg)')

with open("apps/discord_bot/src/plugins/admin.py", "w", encoding="utf-8") as f:
    f.write(content)
