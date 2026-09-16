import re

file_path = r'D:\proyectos_dev\server_rcon_automation\apps\api_rcon\src\connections\databases\migrations\versions\7ea26e120206_add_player_fields.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('import sqlalchemy as sa', 'import sqlalchemy as sa\nimport sqlmodel')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
