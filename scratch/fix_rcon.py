with open("d:/proyectos_dev/matefield_bot/apps/api_rcon/src/connections/apis/rcon.py", "r", encoding="utf-8") as f:
    rcon_code = f.read()

replacement = """        if insert_idx == -1:
            new_lines.append('')
            new_lines.append('[/Script/WDGame.WDGameSession]')
            insert_idx = len(new_lines) - 1
            
        if insert_idx != -1:"""
rcon_code = rcon_code.replace("        if insert_idx != -1:", replacement)

with open("d:/proyectos_dev/matefield_bot/apps/api_rcon/src/connections/apis/rcon.py", "w", encoding="utf-8") as f:
    f.write(rcon_code)
print("Fixed rcon sync_banned_slots logic")
