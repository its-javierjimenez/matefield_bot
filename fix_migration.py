import os
import glob

migration_files = glob.glob(r'd:\proyectos_dev\server_rcon_automation\apps\api_rcon\src\connections\databases\migrations\versions\*_add_observations_column_to_players.py')
if migration_files:
    file = migration_files[0]
    with open(file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if 'import sqlmodel' not in content:
        content = content.replace('import sqlalchemy as sa', 'import sqlalchemy as sa\nimport sqlmodel')
        with open(file, 'w', encoding='utf-8') as f:
            f.write(content)
        print("Fixed", file)
