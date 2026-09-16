import asyncio
from httpx import AsyncClient
async def test():
    async with AsyncClient(base_url="http://localhost:8000") as client:
        res = await client.get("/api/v1/db/players/steam/76561198055320029")
        print(res.json())
asyncio.run(test())
