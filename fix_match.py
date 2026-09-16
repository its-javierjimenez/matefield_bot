import re

file_path = r'D:\proyectos_dev\server_rcon_automation\apps\discord_bot\src\plugins\match.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix broken newlines in strings
content = content.replace('embed_status.description = f"📛 **Nombre:** {server_name}\n\n🔗 **ID para unirse:** {server_id}"', 'embed_status.description = f"📛 **Nombre:** {server_name}\\n\\n🔗 **ID para unirse:** {server_id}"')
content = content.replace('p_text = "`\n" + "\n".join(p_lines) + "\n`" if p_lines else "`\nVacío\n`"', 'p_text = "`\\n" + "\\n".join(p_lines) + "\\n`" if p_lines else "`\\nVacío\\n`"')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
