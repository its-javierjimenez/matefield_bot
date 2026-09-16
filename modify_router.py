file_path = r'd:\proyectos_dev\matefield_bot\apps\api_rcon\src\modules\v1\router.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

target = '''        m.is_active = False
        session.add(m)
        
        if m.special_role_id:
            other_active = (await session.exec(select(Membership).where(
                Membership.steam_id == m.steam_id,
                Membership.special_role_id == m.special_role_id,
                Membership.is_active == True,
                Membership.id != m.id
            ))).first()
            if not other_active:
                pr = (await session.exec(select(PlayerRole).where(
                    PlayerRole.steam_id == m.steam_id,
                    PlayerRole.role_id == m.special_role_id
                ))).first()
                if pr:
                    await session.delete(pr)
                    
    if expired:'''

replacement = '''        m.is_active = False
        session.add(m)
                    
    if expired:'''

if target in content:
    content = content.replace(target, replacement)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print('File updated successfully.')
else:
    print('Target string not found.')
