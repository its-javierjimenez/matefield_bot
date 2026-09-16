with open("d:/proyectos_dev/matefield_bot/apps/discord_bot/src/plugins/admin.py", "r", encoding="utf-8") as f:
    content = f.read()

bad_line1 = "member = plugin.app.cache.get_member(ctx.guild_id, discord_id) or await ctx.app.rest.fetch_member(ctx.guild_id, discord_id)"
good_line1 = """guild_id = ctx.guild_id
                        if not guild_id:
                            return
                        member = plugin.app.cache.get_member(guild_id, discord_id) or await ctx.app.rest.fetch_member(guild_id, discord_id)"""

content = content.replace(bad_line1, good_line1)
with open("d:/proyectos_dev/matefield_bot/apps/discord_bot/src/plugins/admin.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Replaced member fetch logic")
