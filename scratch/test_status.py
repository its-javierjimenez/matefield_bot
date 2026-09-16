import asyncio
import aiohttp

async def main():
    async with aiohttp.ClientSession() as session:
        async with session.get("http://localhost:8000/api/v1/status", headers={"X-API-Key": "secret_dev_key"}) as resp:
            print(await resp.text())

asyncio.run(main())
