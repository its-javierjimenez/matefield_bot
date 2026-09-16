import httpx
import asyncio

async def main():
    headers = {'X-API-Key': 'secret_dev_key'}
    async with httpx.AsyncClient() as client:
        # trigger sync
        print('Triggering sync...')
        res = await client.post('http://localhost:8000/api/v1/db/sync_memberships', headers=headers)
        print('Sync result:', res.status_code)
        
        # Verify
        res = await client.get('http://localhost:8000/api/v1/reserved-slots', headers=headers)
        data = res.json()
        slots = data.get('reservedSlots', [])
        print('Total slots in RCON:', len(slots))
        print('Is juani (76561199521318701) there?', '76561199521318701' in slots)

if __name__ == '__main__':
    asyncio.run(main())
