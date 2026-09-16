with open("apps/discord_bot/src/api_client.py", "r", encoding="utf-8") as f:
    content = f.read()

import re

# Update ban_player
old_ban_player = """    async def ban_player(self, steam_id: str, reason: str) -> bool:
        data = await self._request("POST", f"/api/v1/players/{steam_id}/ban", json={"reason": reason})
        return data.get("ok", False)"""

new_ban_player = """    async def ban_player(self, steam_id: str, reason: str, duration_days: int = 0) -> bool:
        payload = {"reason": reason}
        if duration_days > 0:
            payload["duration_days"] = duration_days
        data = await self._request("POST", f"/api/v1/players/{steam_id}/ban", json=payload)
        return data.get("ok", False)"""

content = content.replace(old_ban_player, new_ban_player)

with open("apps/discord_bot/src/api_client.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Updated api_client.py")
