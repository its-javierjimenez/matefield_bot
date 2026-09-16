with open("apps/discord_bot/src/plugins/admin.py", "r", encoding="utf-8") as f:
    content = f.read()

# Add @ban_group.child before BanPlayer
content = content.replace('\n@crescent.command(name="add", description="Banea a un jugador por Steam ID y sincroniza con RCON")', '\n@ban_group.child\n@crescent.command(name="add", description="Banea a un jugador por Steam ID y sincroniza con RCON")')

with open("apps/discord_bot/src/plugins/admin.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Fixed admin.py ban_group child")
