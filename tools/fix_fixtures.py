import re

files = ['apps/api_rcon/tests/test_sync.py', 'apps/api_rcon/tests/test_crud.py']

for file in files:
    with open(file, 'r', encoding='utf-8') as f:
        content = f.read()

    if 'import pytest_asyncio' not in content:
        content = content.replace('import pytest', 'import pytest\nimport pytest_asyncio')

    content = content.replace('@pytest.fixture(name="session")', '@pytest_asyncio.fixture(name="session")')
    content = content.replace('@pytest.fixture(name="client")', '@pytest_asyncio.fixture(name="client")')
    
    # Mark async test functions
    content = re.sub(r'(async def test_\w+\()', r'@pytest.mark.asyncio\n\1', content)

    with open(file, 'w', encoding='utf-8') as f:
        f.write(content)
