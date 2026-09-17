with open("d:/proyectos_dev/matefield_bot/apps/api_rcon/src/sync_engine.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

with open("d:/proyectos_dev/matefield_bot/apps/api_rcon/src/sync_engine.py", "w", encoding="utf-8") as f:
    for line in lines:
        if "from sqlmodel import select" in line and line.strip().startswith("from sqlmodel"):
            if "        " in line: # It's indented (the local one)
                continue
        f.write(line)
print("Success removing local import!")
