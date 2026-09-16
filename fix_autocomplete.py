import re
file_path = r'D:\proyectos_dev\server_rcon_automation\apps\discord_bot\src\plugins\database.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

replacement = '''
async def autocomplete_tipo(
    ctx: crescent.AutocompleteContext, option: hikari.AutocompleteInteractionOption
) -> list[tuple[str, str]]:
    tipos = ["VIP_COMUN", "VIP_EXPRESS", "VIP_PERMANENTE"]
    try:
        val = str(option.value).lower()
        return [(t, t) for t in tipos if val in t.lower()]
    except Exception:
        return [(t, t) for t in tipos]
'''

# Find the old autocomplete_tipo and replace it
# It was:
# async def autocomplete_tipo(
#     ctx: crescent.AutocompleteContext, option: hikari.AutocompleteInteractionOption
# ) -> list[hikari.CommandChoice]:
#     tipos = ["MENSUAL", "PERMANENTE", "TRIMESTRAL", "ANUAL"]
#     return [hikari.CommandChoice(name=t, value=t) for t in tipos if option.value.lower() in t.lower()]

import re
content = re.sub(r'async def autocomplete_tipo.*?return \[hikari.CommandChoice.*?\]\n', replacement[1:], content, flags=re.DOTALL)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
