with open("apps/discord_bot/src/plugins/account.py", "r", encoding="utf-8") as f:
    content = f.read()

import re

old_stats = """        # Stats
        if stats_data:
            kills = stats_data.get("total_kills", 0)
            deaths = stats_data.get("total_deaths", 0)
            cash = stats_data.get("total_cash", 0)
            matches = stats_data.get("matches_played", 0)
            embed.add_field(name="🏆 Estadísticas Históricas", value=f"**Partidas jugadas:** {matches}\n**Kills:** {kills} | **Deaths:** {deaths}\n**Cash total:** 💲{cash}", inline=False)
            
        await ctx.respond(embed=embed)"""

new_stats = """        # Stats
        if stats_data:
            kills = stats_data.get("total_kills", 0)
            deaths = stats_data.get("total_deaths", 0)
            cash = stats_data.get("total_cash_earned", 0) # Fixed key
            matches = stats_data.get("matches_played", 0)
            playtime = stats_data.get("total_playtime_seconds", 0)
            
            hours = playtime // 3600
            minutes = (playtime % 3600) // 60
            playtime_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
            if playtime == 0: playtime_str = "0m"
            
            embed.add_field(
                name="🏆 Estadísticas Históricas", 
                value=f"**Tiempo de juego:** {playtime_str}\n**Partidas jugadas:** {matches}\n**Kills:** {kills} | **Deaths:** {deaths}\n**Cash total:** 💲{cash}", 
                inline=False
            )
            
        await ctx.respond(embed=embed)"""

content = content.replace(old_stats, new_stats)

with open("apps/discord_bot/src/plugins/account.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Updated account.py")
