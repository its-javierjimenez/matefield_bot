with open("apps/discord_bot/src/api_client.py", "r", encoding="utf-8") as f:
    content = f.read()

import re

old_block = """        async def get_db_bans(self, steam_id: Optional[str] = None) -> schemas.DbBansResponse:
        url = "/api/v1/db/bans"
        if steam_id:
            url += f"?steam_id={steam_id}"
        data = await self._request("GET", url)
        return schemas.DbBansResponse.model_validate(data)"""

new_block = """    async def get_db_bans(self, steam_id: Optional[str] = None) -> schemas.DbBansResponse:
        url = "/api/v1/db/bans"
        if steam_id:
            url += f"?steam_id={steam_id}"
        data = await self._request("GET", url)
        return schemas.DbBansResponse.model_validate(data)"""

content = content.replace(old_block, new_block)

with open("apps/discord_bot/src/api_client.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Fixed api_client.py")
