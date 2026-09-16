import re

with open("d:/proyectos_dev/matefield_bot/apps/api_rcon/src/connections/apis/rcon.py", "r", encoding="utf-8") as f:
    content = f.read()

new_method = """    async def get_bans(self) -> list[str]:
        config = await self.get_config()
        text = config.text or ""
        lines = text.split('\\n')
        bans = []
        for line in lines:
            line = line.strip()
            if line.startswith('.DefaultBannedPlayerIds='):
                val = line.split('=', 1)[1].strip()
                if val:
                    bans.append(val)
            elif line.startswith('+DefaultBannedPlayerIds='):
                val = line.split('=', 1)[1].strip()
                if val:
                    bans.append(val)
        return bans

    async def sync_banned_slots"""

if "async def get_bans(" not in content:
    content = content.replace("    async def sync_banned_slots", new_method)
    with open("d:/proyectos_dev/matefield_bot/apps/api_rcon/src/connections/apis/rcon.py", "w", encoding="utf-8") as f:
        f.write(content)
    print("Added get_bans method")
