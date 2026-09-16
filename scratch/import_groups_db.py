with open("apps/discord_bot/src/plugins/database.py", "r", encoding="utf-8") as f:
    content = f.read()

import re

# Replace group definitions with imports
groups_to_remove = [
    r'membership_group\s*=\s*crescent\.Group\(.*?\)\n',
    r'special_role_group\s*=\s*crescent\.Group\(.*?\)\n',
    r'leaderboard_group\s*=\s*crescent\.Group\(.*?\)\n',
    r'player_group\s*=\s*crescent\.Group\(.*?\)\n',
    r'server_group\s*=\s*crescent\.Group\(.*?\)\n',
]

for g in groups_to_remove:
    content = re.sub(g, '', content)

# Add import
import_stmt = "from src.groups import membership_group, special_role_group, leaderboard_group, player_group, server_group\n"
content = content.replace('plugin = crescent.Plugin()\n', 'plugin = crescent.Plugin()\n' + import_stmt)

with open("apps/discord_bot/src/plugins/database.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Updated database.py groups")
