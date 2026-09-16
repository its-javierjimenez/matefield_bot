with open("apps/discord_bot/src/plugins/account.py", "r", encoding="utf-8") as f:
    content = f.read()

import re

# Remove local player_group
content = re.sub(r'player_group\s*=\s*crescent\.Group\(.*?\)\n', '', content)

# Add imports
import_stmt = "from src.groups import player_group\n"
content = content.replace('plugin = crescent.Plugin[hikari.GatewayBot, Model]()\n', 'plugin = crescent.Plugin[hikari.GatewayBot, Model]()\n' + import_stmt)

# set_welcome_message -> player welcome_message_set
content = content.replace('@crescent.command(name="set_welcome_message"', '@player_group.child\n@crescent.command(name="welcome_message_set"')

with open("apps/discord_bot/src/plugins/account.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Updated account.py groups")
