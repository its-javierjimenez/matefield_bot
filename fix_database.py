import re

file_path = r'D:\proyectos_dev\server_rcon_automation\apps\discord_bot\src\plugins\database.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Add autocomplete_tipo at the top of the plugin block
auto_func = '''
async def autocomplete_tipo(
    ctx: crescent.AutocompleteContext, option: hikari.AutocompleteInteractionOption
) -> list[hikari.CommandChoice]:
    tipos = ["MENSUAL", "PERMANENTE", "TRIMESTRAL", "ANUAL"]
    return [hikari.CommandChoice(name=t, value=t) for t in tipos if option.value.lower() in t.lower()]

'''

if "async def autocomplete_tipo" not in content:
    content = content.replace('plugin = crescent.Plugin()', 'plugin = crescent.Plugin()\n' + auto_func)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
