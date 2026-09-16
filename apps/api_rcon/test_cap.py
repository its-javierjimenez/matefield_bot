import asyncio
import dotenv
dotenv.load_dotenv('../../.env.prod')
from src.connections.apis.rcon import rcon_client

async def main():
    try:
        cap = await rcon_client._request('GET', '/v1/capabilities')
        print(cap.get('routes'))
    except Exception as e:
        print(e)

if __name__ == '__main__':
    asyncio.run(main())
