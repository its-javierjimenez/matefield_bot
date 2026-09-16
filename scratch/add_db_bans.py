with open("apps/api_rcon/src/modules/v1/router.py", "r", encoding="utf-8") as f:
    content = f.read()

import re

new_endpoint = """
@router.get("/db/bans", dependencies=[Depends(verify_api_key_guard)], response_model=schemas.DbBansResponse)
async def get_db_bans(steam_id: Optional[str] = None, session: AsyncSession = Depends(get_session)):
    stmt = select(Ban).where(Ban.is_active == True)
    if steam_id:
        stmt = stmt.where(Ban.steam_id == steam_id)
        
    bans = (await session.exec(stmt)).all()
    
    result = []
    for b in bans:
        result.append(schemas.DbBan(
            id=b.id,
            steam_id=b.steam_id,
            reason=b.reason,
            is_active=b.is_active,
            banned_at=b.banned_at.isoformat() if b.banned_at else ""
        ))
        
    return schemas.DbBansResponse(bans=result)
"""

if "@router.get(\"/db/bans\"" not in content:
    content += new_endpoint

with open("apps/api_rcon/src/modules/v1/router.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Updated router.py with GET /db/bans")
