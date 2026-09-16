import re

file_path = r'D:\proyectos_dev\server_rcon_automation\apps\discord_bot\src\plugins\account.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix broken newlines in strings
content = content.replace('mem_str = "\n".join', 'mem_str = "\\n".join')
content = content.replace('roles_str = "\n".join', 'roles_str = "\\n".join')
content = content.replace('value=f"`\n{obs}\n`"', 'value=f"`\\n{obs}\\n`"')
content = content.replace('value=f"**Partidas jugadas:** {matches}\n**Kills:** {kills} | **Deaths:** {deaths}\n**Cash total:** "', 'value=f"**Partidas jugadas:** {matches}\\n**Kills:** {kills} | **Deaths:** {deaths}\\n**Cash total:** "')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
