with open("scratch/moved_commands.py", "r", encoding="utf-8") as f:
    moved = f.read()

# Replace decorators for moved commands
moved = moved.replace('@crescent.command(name="sync_memberships"', '@membership_group.child\n@crescent.command(name="sync"')
moved = moved.replace('@crescent.command(name="compensar_todos"', '@membership_group.child\n@crescent.command(name="compensate_all"')
moved = moved.replace('@crescent.command(name="extender_membresia"', '@membership_group.child\n@crescent.command(name="extend"')

with open("apps/discord_bot/src/plugins/database.py", "a", encoding="utf-8") as f:
    f.write("\n" + moved)
print("Appended moved commands to database.py")
