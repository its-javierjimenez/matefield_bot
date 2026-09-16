with open("apps/discord_bot/src/plugins/match.py", "r", encoding="utf-8") as f:
    content = f.read()

import re

# Add imports
import_stmt = "from src.groups import match_group, server_group\n"
content = content.replace('plugin = crescent.Plugin()\n', 'plugin = crescent.Plugin()\n' + import_stmt)

# Match status -> match status
content = content.replace('@crescent.command(name="status"', '@match_group.child\n@crescent.command(name="status"')
# match players -> match players
content = content.replace('@crescent.command(name="players"', '@match_group.child\n@crescent.command(name="players"')
# match leaderboard -> match leaderboard
content = content.replace('@crescent.command(name="leaderboard"', '@match_group.child\n@crescent.command(name="leaderboard"')
# match player -> match player_info
content = content.replace('@crescent.command(name="player"', '@match_group.child\n@crescent.command(name="player_info"')
# server logs -> server logs
content = content.replace('@crescent.command(name="logs"', '@server_group.child\n@crescent.command(name="logs"')

with open("apps/discord_bot/src/plugins/match.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Updated match.py groups")
