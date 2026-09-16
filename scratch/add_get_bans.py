with open("apps/api_rcon/src/connections/apis/rcon.py", "r", encoding="utf-8") as f:
    content = f.read()

import re

old_get = """    async def get_reserved_slots(self) -> schemas.ReservedSlots:
        async def fetch():
            data = await self._request("GET", "/v1/reservedslots")
            return schemas.ReservedSlots.model_validate(data)
        return await self._get_cached("reservedslots", fetch)"""

new_get = """    async def get_reserved_slots(self) -> schemas.ReservedSlots:
        async def fetch():
            data = await self._request("GET", "/v1/reservedslots")
            return schemas.ReservedSlots.model_validate(data)
        return await self._get_cached("reservedslots", fetch)

    async def get_bans(self) -> schemas.Bans:
        async def fetch():
            data = await self._request("GET", "/v1/bans")
            return schemas.Bans.model_validate(data)
        return await self._get_cached("bans", fetch)"""

content = content.replace(old_get, new_get)

with open("apps/api_rcon/src/connections/apis/rcon.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Added get_bans to rcon.py")
