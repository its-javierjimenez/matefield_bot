import re
file_path = r'D:\proyectos_dev\server_rcon_automation\apps\discord_bot\src\plugins\database.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

replacement = '''
@plugin.include
@db_group.child
@crescent.command(name="add_membership", description="Añade una membresía VIP a un jugador vinculado")
class DbAddMembership:
'''

content = content.replace('class DbAddMembership:\n', replacement[1:])

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
