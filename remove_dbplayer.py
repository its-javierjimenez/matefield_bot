import re

with open('d:/proyectos_dev/server_rcon_automation/apps/discord_bot/src/plugins/database.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Match @plugin.include\n@db_group.child\n@crescent.command(name="player"...\nclass DbPlayer: ... until next @plugin.include
pattern = r'(?:@plugin\.include\s*\n\s*)?@db_group\.child\s*\n\s*@crescent\.command\(name="player".*?\nclass DbPlayer:(?:\s+.*?\n)+?(?=\s*@plugin\.include|\s*@db_group\.child|$)'
new_content = re.sub(pattern, '', content)

with open('d:/proyectos_dev/server_rcon_automation/apps/discord_bot/src/plugins/database.py', 'w', encoding='utf-8') as f:
    f.write(new_content)
