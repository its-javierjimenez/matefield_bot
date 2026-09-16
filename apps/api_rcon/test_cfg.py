import asyncio
import dotenv
dotenv.load_dotenv('../../.env.prod')
from src.connections.apis.rcon import rcon_client

async def main():
    try:
        config = await rcon_client.get_config()
        if 'DefaultBannedPlayerIds' in config.text:
            print('Found DefaultBannedPlayerIds in config')
        else:
            print('Not found')
    except Exception as e:
        print(e)

if __name__ == '__main__':
    asyncio.run(main())
