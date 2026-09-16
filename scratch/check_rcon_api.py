import asyncio
import aiohttp

async def main():
    headers = {"Authorization": "Bearer dVt2ajQzYqGKnDft"}
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get("http://169.155.127.77:9001/v1/players") as resp:
            print(f"Status: {resp.status}")
            print(await resp.text())

if __name__ == '__main__':
    asyncio.run(main())
