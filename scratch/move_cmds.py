with open("apps/discord_bot/src/plugins/admin.py", "r", encoding="utf-8") as f:
    content = f.read()

import re

match1 = re.search(r'(@plugin\.include\n@crescent\.hook\(admin_only\)\n@crescent\.command\(name="sync_memberships".*?)(?=@plugin\.include)', content, re.DOTALL)
match2 = re.search(r'(@plugin\.include\n@crescent\.hook\(admin_only\)\n@crescent\.command\(name="compensar_todos".*?)(?=@plugin\.include)', content, re.DOTALL)
match3 = re.search(r'(@plugin\.include\n@crescent\.hook\(admin_only\)\n@crescent\.command\(name="extender_membresia".*?)(?=@plugin\.include)', content, re.DOTALL)

if match1 and match2 and match3:
    print("Found all 3 commands")
    with open("scratch/moved_commands.py", "w", encoding="utf-8") as out:
        out.write(match1.group(1))
        out.write("\n")
        out.write(match2.group(1))
        out.write("\n")
        out.write(match3.group(1))
        
    # Remove them from admin.py
    new_content = content.replace(match1.group(1), "")
    new_content = new_content.replace(match2.group(1), "")
    new_content = new_content.replace(match3.group(1), "")
    with open("apps/discord_bot/src/plugins/admin.py", "w", encoding="utf-8") as f:
        f.write(new_content)
    print("Removed from admin.py")
else:
    print("Could not find all commands")
