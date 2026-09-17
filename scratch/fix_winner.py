import re

with open("d:/proyectos_dev/matefield_bot/apps/api_rcon/src/sync_engine.py", "r", encoding="utf-8") as f:
    engine_code = f.read()

replacement = """                    # Close old match if it exists
                    if current_match_id:
                        old_match = await session.get(Match, current_match_id)
                        if old_match and old_match.end_time is None:
                            old_match.end_time = datetime.datetime.now(datetime.timezone.utc)
                            # Determine winning team from last known MatchTeamStats
                            from sqlmodel import select
                            winner_stmt = select(MatchTeamStats).where(MatchTeamStats.match_id == current_match_id).order_by(MatchTeamStats.score.desc())
                            winner_stat = (await session.exec(winner_stmt)).first()
                            if winner_stat:
                                old_match.winning_team_id = winner_stat.team_id
                            session.add(old_match)"""

# Search for the old code to replace
old_code_pattern = r"                    # Close old match if it exists.*?session\.add\(old_match\)"

engine_code = re.sub(old_code_pattern, replacement, engine_code, flags=re.DOTALL)

with open("d:/proyectos_dev/matefield_bot/apps/api_rcon/src/sync_engine.py", "w", encoding="utf-8") as f:
    f.write(engine_code)
print("Updated sync_engine.py to assign winning team on map change")
