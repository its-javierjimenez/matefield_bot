with open("apps/discord_bot/src/plugins/config.py", "r", encoding="utf-8") as f:
    content = f.read()

import re

# Replace group definitions with imports
groups_to_remove = [
    r'config_group\s*=\s*crescent\.Group\(.*?\)\n',
    r'vip_role_group\s*=\s*crescent\.Group\(.*?\)\n',
    r'role_map_group\s*=\s*crescent\.Group\(.*?\)\n',
    r'whitelist_group\s*=\s*crescent\.Group\(.*?\)\n',
]

for g in groups_to_remove:
    content = re.sub(g, '', content)

# Add import
import_stmt = "from src.groups import config_group, vip_role_group, role_map_group, whitelist_group\n"
content = content.replace('plugin = crescent.Plugin()\n', 'plugin = crescent.Plugin()\n' + import_stmt)

with open("apps/discord_bot/src/plugins/config.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Updated config.py groups")
