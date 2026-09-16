with open("d:/proyectos_dev/matefield_bot/apps/discord_bot/src/plugins/config.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if '**Roles de Baneos:**' in line and line.strip().endswith('"**Roles de Baneos:**'):
        # This line has a literal newline - merge with next line
        next_line = lines[i+1] if i+1 < len(lines) else ""
        # Replace with proper escaped newline
        lines[i] = '        await ctx.respond("**Roles de Baneos:\\n" + "\\n".join(lines))\n'
        lines[i+1] = ""
        break

with open("d:/proyectos_dev/matefield_bot/apps/discord_bot/src/plugins/config.py", "w", encoding="utf-8") as f:
    f.writelines(lines)
print("Fixed")
