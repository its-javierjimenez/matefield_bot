with open("apps/discord_bot/src/plugins/admin.py", "r", encoding="utf-8") as f:
    content = f.read()

import re

# Replace group definitions with imports
groups_to_remove = [
    r'ban_group\s*=\s*crescent\.Group\(.*?\)\n',
    r'quota_group\s*=\s*crescent\.Group\(.*?\)\n',
    r'server_group\s*=\s*crescent\.Group\(.*?\)\n',
    r'hacker_group\s*=\s*crescent\.Group\(.*?\)\n',
    r'reserved_group\s*=\s*crescent\.Group\(.*?\)\n',
]

for g in groups_to_remove:
    content = re.sub(g, '', content)

# Add import
import_stmt = "from src.groups import ban_group, quota_group, server_group, hacker_group, reserved_group\n"
content = content.replace('plugin = crescent.Plugin()\n', 'plugin = crescent.Plugin()\n' + import_stmt)

with open("apps/discord_bot/src/plugins/admin.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Updated admin.py groups")
