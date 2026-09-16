with open("apps/discord_bot/src/plugins/admin.py", "r", encoding="utf-8") as f:
    admin_content = f.read()

admin_content = admin_content.replace('await ctx.respond(current_msg)', 'await ctx.respond(current_msg, ephemeral=True)')

with open("apps/discord_bot/src/plugins/admin.py", "w", encoding="utf-8") as f:
    f.write(admin_content)

print("Fixes applied to admin.py.")
