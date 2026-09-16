with open("d:/proyectos_dev/matefield_bot/apps/discord_bot/src/plugins/database.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

for idx in [127, 508, 509, 510, 511]:
    if "# type: ignore" not in lines[idx]:
        lines[idx] = lines[idx].rstrip("\r\n ") + " # type: ignore\n"

with open("d:/proyectos_dev/matefield_bot/apps/discord_bot/src/plugins/database.py", "w", encoding="utf-8") as f:
    f.writelines(lines)

print("Applied exact line fixes for database.py")
