import asyncio
from rcon.source import rcon

async def main():
    try:
        res = await rcon("ShowPlayers", host="169.155.127.77", port=9001, passwd="matefieldrcon")
        print(res)
    except Exception as e:
        print("Error:", e)

if __name__ == '__main__':
    asyncio.run(main())
