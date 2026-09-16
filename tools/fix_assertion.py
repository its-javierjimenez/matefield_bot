with open('apps/api_rcon/tests/test_sync.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('"active_memberships": []}', '"active_memberships": [], "special_roles": []}')

with open('apps/api_rcon/tests/test_sync.py', 'w', encoding='utf-8') as f:
    f.write(content)
