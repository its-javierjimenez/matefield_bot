with open("apps/api_rcon/src/connections/databases/db.py", "r", encoding="utf-8") as f:
    content = f.read()

import re

new_ban = """class Ban(SQLModel, table=True):
    __tablename__ = "bans"
    id: Optional[int] = Field(default=None, primary_key=True)
    steam_id: str = Field(foreign_key="players.steam_id", index=True)
    reason: str
    is_active: bool = Field(default=True)
    rcon_sync_status: str = Field(default="PENDING")
    banned_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True)))
    expires_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True)))"""

old_ban_pattern = r'class Ban\(SQLModel, table=True\):\n    __tablename__ = "bans".*?banned_at: datetime = Field\(.*? sa_column=Column\(DateTime\(timezone=True\)\)\)'

match = re.search(old_ban_pattern, content, re.DOTALL)
if match:
    content = content.replace(match.group(0), new_ban)
    with open("apps/api_rcon/src/connections/databases/db.py", "w", encoding="utf-8") as f:
        f.write(content)
    print("Updated db.py")
else:
    print("Could not find Ban class")
