with open("apps/discord_bot/src/plugins/admin.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    if line.strip() == 'msg = f"**Jugadores Baneados ({len(bans)}):**' and lines[i+1].strip() == '"':
        new_lines.append('            msg = f"**Jugadores Baneados ({len(bans)}):**\\n"\n')
        lines[i+1] = '' # skip next
    elif line.strip() == 'current_msg += line + "' and lines[i+1].strip() == '"':
        new_lines.append('                current_msg += line + "\\n"\n')
        lines[i+1] = '' # skip next
    else:
        new_lines.append(line)

with open("apps/discord_bot/src/plugins/admin.py", "w", encoding="utf-8") as f:
    f.writelines(new_lines)
print("Fixed admin.py string literals")
