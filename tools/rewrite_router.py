import re

with open('apps/api_rcon/src/modules/v1/router.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace Session with AsyncSession in Depends
content = re.sub(r'def (\w+)\((.*?)session: Session = Depends\(get_session\)\):', r'async def \1(\2session: AsyncSession = Depends(get_session)):', content)

# Replace session methods with await
content = re.sub(r'session\.get\(', r'await session.get(', content)
content = re.sub(r'session\.exec\(', r'await session.exec(', content)
content = re.sub(r'session\.commit\(', r'await session.commit(', content)
content = re.sub(r'session\.refresh\(', r'await session.refresh(', content)

# Update imports
content = content.replace("from sqlmodel import Session", "from sqlmodel.ext.asyncio.session import AsyncSession")
if "from sqlmodel.ext.asyncio.session import AsyncSession" not in content:
    content = content.replace("from sqlmodel import select", "from sqlmodel import select\nfrom sqlmodel.ext.asyncio.session import AsyncSession")

with open('apps/api_rcon/src/modules/v1/router.py', 'w', encoding='utf-8') as f:
    f.write(content)
