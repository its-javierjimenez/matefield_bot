import os
import aiohttp
from typing import Optional, Dict, Any, List

STEAM_API_KEY = os.environ.get("STEAM_WEB_API_KEY")

async def get_player_summary(steam_id: str) -> Optional[Dict[str, Any]]:
    """Obtiene el resumen (nombre y avatar) de un jugador usando la API de Steam."""
    summaries = await get_player_summaries([steam_id])
    return summaries.get(steam_id)

async def get_player_summaries(steam_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """Obtiene el resumen de multiples jugadores (hasta 100). Devuelve un diccionario {steamid: summary}."""
    if not STEAM_API_KEY or not steam_ids:
        return {}
        
    url = "http://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/"
    
    # Steam API supports up to 100 comma-separated IDs
    results = {}
    for i in range(0, len(steam_ids), 100):
        chunk = steam_ids[i:i+100]
        params = {
            "key": STEAM_API_KEY,
            "steamids": ",".join(chunk)
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        players = data.get("response", {}).get("players", [])
                        for p in players:
                            results[p["steamid"]] = p
        except Exception as e:
            import logging
            logging.getLogger("steam_api").error(f"Error fetching steam profiles for chunk: {e}")
            
    return results
