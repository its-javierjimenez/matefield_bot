with open("apps/discord_bot/src/plugins/database.py", "r", encoding="utf-8") as f:
    db_content = f.read()

db_content = db_content.replace('desc = "\n".join(lines)', 'desc = "\\n".join(lines)')

with open("apps/discord_bot/src/plugins/database.py", "w", encoding="utf-8") as f:
    f.write(db_content)

with open("apps/discord_bot/src/plugins/admin.py", "r", encoding="utf-8") as f:
    admin_content = f.read()

admin_content = admin_content.replace('msg = "**Jugadores en Slots Reservados:**\n"', 'msg = "**Jugadores en Slots Reservados:**\\n"')
admin_content = admin_content.replace('current_msg += line + "\n"', 'current_msg += line + "\\n"')

with open("apps/discord_bot/src/plugins/admin.py", "w", encoding="utf-8") as f:
    f.write(admin_content)

print("Fixes applied.")
