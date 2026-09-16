import re

file_path = r'C:\Users\itsja\.gemini\antigravity-ide\brain\ca324d82-d5f3-4a77-b8f9-66b54c7148af\scratch\sync_vips.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('PlayerRole.player_id == steam_id', 'PlayerRole.steam_id == steam_id')
content = content.replace('new_link = PlayerRole(player_id=steam_id, role_id=fundador_role.id)', 'new_link = PlayerRole(steam_id=steam_id, role_id=fundador_role.id)')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
