with open("apps/api_rcon/src/modules/v1/router.py", "r", encoding="utf-8") as f:
    content = f.read()

import re

old_stats = """@router.get("/db/players/steam/{steam_id}/stats", dependencies=[Depends(verify_api_key_guard)])
async def get_player_stats_by_steam(steam_id: str, session: AsyncSession = Depends(get_session)):
    statement = (
        select(
            func.sum(MatchPlayerStats.kills).label("total_kills"),
            func.sum(MatchPlayerStats.deaths).label("total_deaths"),
            func.sum(MatchPlayerStats.cash_earned).label("total_cash_earned")
        )
        .where(MatchPlayerStats.steam_id == steam_id)
    )
    result = ((await session.exec(statement))).first()
    
    if not result or result[0] is None:
        return {"total_kills": 0, "total_deaths": 0, "total_cash_earned": 0}
        
    return {
        "total_kills": int(result[0] or 0),
        "total_deaths": int(result[1] or 0),
        "total_cash_earned": int(result[2] or 0)
    }"""

new_stats = """@router.get("/db/players/steam/{steam_id}/stats", dependencies=[Depends(verify_api_key_guard)])
async def get_player_stats_by_steam(steam_id: str, session: AsyncSession = Depends(get_session)):
    # Get match stats
    statement = (
        select(
            func.sum(MatchPlayerStats.kills).label("total_kills"),
            func.sum(MatchPlayerStats.deaths).label("total_deaths"),
            func.sum(MatchPlayerStats.cash_earned).label("total_cash_earned"),
            func.count(MatchPlayerStats.id).label("matches_played")
        )
        .where(MatchPlayerStats.steam_id == steam_id)
    )
    result = ((await session.exec(statement))).first()
    
    # Get playtime
    playtime_stmt = select(func.sum(PlayerSession.total_seconds)).where(PlayerSession.steam_id == steam_id)
    playtime_result = (await session.exec(playtime_stmt)).first()
    total_playtime_seconds = int(playtime_result or 0)
    
    return {
        "total_kills": int(result[0] or 0) if result else 0,
        "total_deaths": int(result[1] or 0) if result else 0,
        "total_cash_earned": int(result[2] or 0) if result else 0,
        "matches_played": int(result[3] or 0) if result else 0,
        "total_playtime_seconds": total_playtime_seconds
    }"""

content = content.replace(old_stats, new_stats)

with open("apps/api_rcon/src/modules/v1/router.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Updated router.py")
