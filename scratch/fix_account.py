import re

with open("d:/proyectos_dev/matefield_bot/apps/discord_bot/src/plugins/account.py", "r", encoding="utf-8") as f:
    content = f.read()

# Fix unused ignore at line 18
content = content.replace("usuario = crescent.option(hikari.User, \"Usuario a vincular (Solo admin)\", default=None) # type: ignore", 
                          "usuario = crescent.option(hikari.User, \"Usuario a vincular (Solo admin)\", default=None)")

# Fix target_steam_id by explicitly casting to str
content = content.replace("steam_data = await plugin.model.api.get_player_by_steam(target_steam_id)", 
                          "steam_data = await plugin.model.api.get_player_by_steam(str(target_steam_id))")
content = content.replace("stats_data = await plugin.model.api.get_player_historical_stats(target_steam_id)", 
                          "stats_data = await plugin.model.api.get_player_historical_stats(str(target_steam_id))")

with open("d:/proyectos_dev/matefield_bot/apps/discord_bot/src/plugins/account.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Fixed account.py issues")
