import re

file_path = r'C:\Users\itsja\.gemini\antigravity-ide\brain\ca324d82-d5f3-4a77-b8f9-66b54c7148af\scratch\sync_vips.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('RoleLink', 'PlayerRole')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
