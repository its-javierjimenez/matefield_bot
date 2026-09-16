with open("apps/discord_bot/src/api_client.py", "r", encoding="utf-8") as f:
    content = f.read()

import re

new_method = """    async def get_db_bans(self, steam_id: Optional[str] = None) -> schemas.DbBansResponse:
        url = "/api/v1/db/bans"
        if steam_id:
            url += f"?steam_id={steam_id}"
        data = await self._request("GET", url)
        return schemas.DbBansResponse.model_validate(data)"""

if "def get_db_bans" not in content:
    # Insert after get_audit_logs
    content = content.replace("async def get_audit_logs", new_method + "\n\n    async def get_audit_logs")
    
with open("apps/discord_bot/src/api_client.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Updated api_client.py")
