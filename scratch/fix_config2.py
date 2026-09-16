with open("d:/proyectos_dev/matefield_bot/apps/discord_bot/src/plugins/config.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

# Find and remove the orphaned line
new_lines = []
for i, line in enumerate(lines):
    stripped = line.strip()
    if stripped == '".join(lines))':
        continue  # Skip this orphaned line
    new_lines.append(line)

with open("d:/proyectos_dev/matefield_bot/apps/discord_bot/src/plugins/config.py", "w", encoding="utf-8") as f:
    f.writelines(new_lines)
print("Cleaned up orphaned line")
