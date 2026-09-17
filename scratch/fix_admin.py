import re

with open("d:/proyectos_dev/matefield_bot/apps/api_rcon/src/modules/v1/router.py", "r", encoding="utf-8") as f:
    content = f.read()

old_block = """    # Add special roles to the active_roles list for primary role calculation
    for sr in special_roles:
        active_roles.append(sr.upper())
            
    primary_role = None
    if any("OWNER" in r for r in active_roles):
        primary_role = "OWNER"
    elif any("ADMIN" in r for r in active_roles):
        primary_role = "ADMIN"
    elif any("VIP" in r for r in active_roles):
        primary_role = "VIP"
    elif active_roles:
        primary_role = active_roles[0]"""

new_block = """    # Fetch configs to resolve special role names
    configs_stmt = select(BotConfig).where(BotConfig.config_key.in_(["ADMIN_ROLE_ID", "OWNER_ROLE_ID"]))
    configs = (await session.exec(configs_stmt)).all()
    config_dict = {c.config_key: c.config_value for c in configs}
    
    # Add special roles to the active_roles list for primary role calculation
    for sr in special_roles:
        if config_dict.get("ADMIN_ROLE_ID") == sr:
            active_roles.append("ADMIN")
        elif config_dict.get("OWNER_ROLE_ID") == sr:
            active_roles.append("OWNER")
        else:
            active_roles.append(sr.upper())
            
    primary_role = None
    if any("OWNER" in r for r in active_roles):
        primary_role = "OWNER"
    elif any("ADMIN" in r for r in active_roles):
        primary_role = "ADMIN"
    elif any("VIP" in r for r in active_roles):
        primary_role = "VIP"
    elif active_roles:
        # Prevent numbers from being displayed as role names
        primary_role = active_roles[0] if not active_roles[0].isdigit() else "VIP\"" """

if old_block in content:
    content = content.replace(old_block, new_block)
    with open("d:/proyectos_dev/matefield_bot/apps/api_rcon/src/modules/v1/router.py", "w", encoding="utf-8") as f:
        f.write(content)
    print("Success replacing block!")
else:
    print("Block not found!")
