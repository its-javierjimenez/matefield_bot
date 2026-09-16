with open("apps/discord_bot/src/plugins/admin.py", "r", encoding="utf-8") as f:
    content = f.read()

import re

# Fix the broken f-string if needed
content = content.replace("msg = f\"**Jugadores Baneados ({len(bans)}):**\n\"", "msg = f\"**Jugadores Baneados ({len(bans)}):**\\n\"")

with open("apps/discord_bot/src/plugins/admin.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Fixed admin.py")
