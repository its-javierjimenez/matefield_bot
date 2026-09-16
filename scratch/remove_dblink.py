with open("apps/discord_bot/src/plugins/database.py", "r", encoding="utf-8") as f:
    content = f.read()

start_idx = content.find('class DbLinkPlayer:')
if start_idx != -1:
    start_idx = content.rfind('@plugin.include', 0, start_idx)
    end_idx = content.find('@plugin.include', start_idx + 10)
    
    new_content = content[:start_idx] + content[end_idx:]
    with open("apps/discord_bot/src/plugins/database.py", "w", encoding="utf-8") as f:
        f.write(new_content)
    print("Success: database.py modified")
else:
    print("Error finding DbLinkPlayer")
