with open("d:/proyectos_dev/matefield_bot/apps/discord_bot/src/api_client.py", "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace("async def ban_player(self, steam_id: str, reason: str) -> None:", "async def ban_player(self, steam_id: str, reason: str, duration_days: int = 0) -> None:")
content = content.replace("await self._request(\"POST\", f\"/api/v1/players/{steam_id}/ban\", json={\"reason\": reason})", "await self._request(\"POST\", f\"/api/v1/players/{steam_id}/ban\", json={\"reason\": reason, \"duration_days\": duration_days})")

with open("d:/proyectos_dev/matefield_bot/apps/discord_bot/src/api_client.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Fixed api_client.py ban_player")
