with open("packages/wardogs_schemas/src/wardogs_schemas/v1.py", "r", encoding="utf-8") as f:
    content = f.read()

import re

# Add a DB Ban schema
new_schema = """
class DbBan(BaseModel):
    id: int
    steam_id: str
    reason: str
    is_active: bool
    banned_at: str

class DbBansResponse(BaseModel):
    bans: list[DbBan]
"""
if "DbBan" not in content:
    content += new_schema

with open("packages/wardogs_schemas/src/wardogs_schemas/v1.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Updated schemas")
