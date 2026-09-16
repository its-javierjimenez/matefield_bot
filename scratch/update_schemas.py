with open("packages/wardogs_schemas/src/wardogs_schemas/v1.py", "r", encoding="utf-8") as f:
    content = f.read()

import re

# Update ReasonRequest
old_reason = """class ReasonRequest(BaseModel):
    reason: str | None = None"""
new_reason = """class ReasonRequest(BaseModel):
    reason: str | None = None
    duration_days: int | None = None"""
content = content.replace(old_reason, new_reason)

# Update DbBan
old_db_ban = """class DbBan(BaseModel):
    id: int
    steam_id: str
    reason: str
    is_active: bool
    banned_at: str"""
new_db_ban = """class DbBan(BaseModel):
    id: int
    steam_id: str
    reason: str
    is_active: bool
    banned_at: str
    expires_at: str | None = None"""
content = content.replace(old_db_ban, new_db_ban)

with open("packages/wardogs_schemas/src/wardogs_schemas/v1.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Updated schemas")
