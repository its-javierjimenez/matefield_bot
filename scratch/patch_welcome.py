with open("apps/discord_bot/src/plugins/account.py", "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace('@crescent.hook(vip_or_admin)\n@player_group.child\n@crescent.command(name="set_welcome_message"', 
                          '@crescent.hook(admin_only)\n@player_group.child\n@crescent.command(name="set_welcome_message"')

with open("apps/discord_bot/src/plugins/account.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Updated set_welcome_message hook")
