import asyncio
import dotenv
dotenv.load_dotenv('../../.env.prod')
from src.connections.apis.rcon import rcon_client

async def main():
    try:
        print('Testing POST /v1/bans...')
        res = await rcon_client._request('POST', '/v1/bans', json={'steamId': '99999999999999999', 'reason': 'Test ban'})
        print('Response:', res)
    except Exception as e:
        print('Error:', e)

if __name__ == '__main__':
    asyncio.run(main())
