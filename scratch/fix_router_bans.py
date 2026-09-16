with open("d:/proyectos_dev/matefield_bot/apps/api_rcon/src/modules/v1/router.py", "r", encoding="utf-8") as f:
    content = f.read()

old_bans = """        rcon_bans_resp = await rcon.get_bans()
        rcon_steam_ids = set([b.steamId for b in rcon_bans_resp.bans if b.steamId]) if rcon_bans_resp.bans else set()"""
new_bans = """        rcon_bans_resp = await rcon.get_bans()
        rcon_steam_ids = set(rcon_bans_resp)"""

content = content.replace(old_bans, new_bans)
with open("d:/proyectos_dev/matefield_bot/apps/api_rcon/src/modules/v1/router.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Fixed router.py line 81")
