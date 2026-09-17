with open("d:/proyectos_dev/matefield_bot/apps/discord_bot/src/plugins/account.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if "> {self.message}\")" in line:
        continue # delete this line
    new_lines.append(line)

with open("d:/proyectos_dev/matefield_bot/apps/discord_bot/src/plugins/account.py", "w", encoding="utf-8") as f:
    f.writelines(new_lines)
print("Fixed syntax error")
