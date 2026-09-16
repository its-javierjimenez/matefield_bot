import aiohttp
import os
from typing import Dict, Any, Optional, List

from wardogs_schemas import v1 as schemas

class APIClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip('/')
        self.headers = {
            "X-API-Key": api_key,
            "Content-Type": "application/json"
        }

    async def _request(self, method: str, endpoint: str, **kwargs) -> Any:
        url = f"{self.base_url}{endpoint}"
        async with aiohttp.ClientSession(headers=self.headers) as session:
            async with session.request(method, url, **kwargs) as response:
                if response.status >= 400:
                    text = await response.text()
                    raise Exception(f"HTTP {response.status}: {text}")
                response.raise_for_status()
                if "application/json" in response.headers.get("Content-Type", ""):
                    return await response.json()
                return await response.text()

    # RCON wrapped endpoints
    async def get_status(self) -> schemas.Status:
        data = await self._request("GET", "/api/v1/status")
        return schemas.Status.model_validate(data)

    async def get_players(self) -> schemas.Players1:
        data = await self._request("GET", "/api/v1/players")
        return schemas.Players1.model_validate(data)

    async def get_db_bans(self, steam_id: Optional[str] = None) -> schemas.DbBansResponse:
        url = "/api/v1/db/bans"
        if steam_id:
            url += f"?steam_id={steam_id}"
        data = await self._request("GET", url)
        return schemas.DbBansResponse.model_validate(data)

    async def get_audit_logs(self, limit: int = 50) -> schemas.Audit:
        data = await self._request("GET", f"/api/v1/audit?limit={limit}")
        return schemas.Audit.model_validate(data)

    async def get_reserved_slots(self) -> schemas.ReservedSlots:
        data = await self._request("GET", "/api/v1/reserved-slots")
        return schemas.ReservedSlots.model_validate(data)

    async def add_reserved_slot(self, steam_id: str) -> None:
        await self._request("POST", "/api/v1/reserved-slots", json={"steamId": steam_id})

    async def remove_reserved_slot(self, steam_id: str) -> None:
        await self._request("DELETE", f"/api/v1/reserved-slots/{steam_id}")

    async def broadcast(self, message: str) -> None:
        await self._request("POST", "/api/v1/broadcast", json={"message": message})

    async def send_player_message(self, steam_id: str, message: str) -> None:
        await self._request("POST", f"/api/v1/players/{steam_id}/message", json={"message": message})

    async def get_config(self) -> schemas.Config1:
        data = await self._request("GET", "/api/v1/config")
        return schemas.Config1.model_validate(data)

    async def update_config(self, revision: str, new_text: str) -> schemas.ConfigResult:
        data = await self._request("PUT", "/api/v1/config", json={"revision": revision, "new_text": new_text})
        return schemas.ConfigResult.model_validate(data)

    # Database endpoints
    async def link_account(self, discord_id: str, steam_id: str) -> None:
        await self._request("POST", "/api/v1/db/players/link", json={"discord_id": discord_id, "steam_id": steam_id})

    async def unlink_account(self, discord_id: str) -> None:
        await self._request("POST", "/api/v1/db/players/unlink", json={"discord_id": discord_id})

    async def get_player_by_discord(self, discord_id: str) -> Optional[Dict[str, Any]]:
        try:
            return await self._request("GET", f"/api/v1/db/players/discord/{discord_id}")
        except Exception as e:
            if "HTTP 404" in str(e):
                return None
            raise

    async def get_player_by_steam(self, steam_id: str) -> Optional[Dict[str, Any]]:
        try:
            return await self._request("GET", f"/api/v1/db/players/steam/{steam_id}")
        except Exception as e:
            if "HTTP 404" in str(e):
                return None
            raise

    async def set_welcome_message(self, steam_id: str, message: str) -> None:
        await self._request("POST", f"/api/v1/db/players/steam/{steam_id}/welcome-message", json={"message": message})

    async def add_membership(self, steam_id: str, membership_type: str, days: Optional[int] = None, special_role: Optional[str] = None) -> None:
        payload = {"steam_id": steam_id, "membership_type": membership_type}
        if days is not None:
            payload["days"] = days
        if special_role:
            payload["special_role"] = special_role
        await self._request("POST", "/api/v1/db/players/membership", json=payload)

    async def edit_membership(self, membership_id: int, days: Optional[int] = None, add_days: Optional[int] = None, membership_type: Optional[str] = None, is_active: Optional[bool] = None) -> None:
        payload = {}
        if days is not None: payload["days"] = days
        if add_days is not None: payload["add_days"] = add_days
        if membership_type is not None: payload["membership_type"] = membership_type
        if is_active is not None: payload["is_active"] = is_active
        await self._request("PUT", f"/api/v1/db/memberships/{membership_id}", json=payload)

    async def compensate_memberships(self, days: int) -> Dict[str, Any]:
        return await self._request("POST", "/api/v1/db/memberships/compensate", json={"days": days})

    async def delete_membership(self, membership_id: int) -> None:
        await self._request("DELETE", f"/api/v1/db/memberships/{membership_id}")

    async def remove_special_role(self, steam_id: str, role_id: str) -> None:
        await self._request("DELETE", f"/api/v1/db/players/{steam_id}/roles/{role_id}")

    async def edit_player(self, steam_id: str, discord_id: Optional[str] = None, custom_welcome_message: Optional[str] = None, observations: Optional[str] = None) -> None:
        payload = {}
        if discord_id is not None: payload["discord_id"] = discord_id
        if custom_welcome_message is not None: payload["custom_welcome_message"] = custom_welcome_message
        if observations is not None: payload["observations"] = observations
        await self._request("PUT", f"/api/v1/db/players/{steam_id}", json=payload)

    async def export_table_csv(self, table_name: str) -> str:
        # Returns raw CSV text
        return await self._request("GET", f"/api/v1/db/export/{table_name}")

    async def sync_memberships(self) -> Dict[str, Any]:
        return await self._request("POST", "/api/v1/db/sync_memberships")

    async def get_leaderboard(self, metric: str = "kills", limit: int = 15) -> Dict[str, Any]:
        return await self._request("GET", f"/api/v1/db/leaderboard?metric={metric}&limit={limit}")

    async def get_bot_config(self, key: str) -> Optional[str]:
        try:
            res = await self._request("GET", f"/api/v1/bot/config/{key}")
            return res.get("value")
        except Exception as e:
            if "HTTP 404" in str(e):
                return None
            raise

    async def get_bot_configs(self) -> Dict[str, str]:
        res = await self._request("GET", "/api/v1/bot/configs")
        return res.get("configs", {})

    async def set_bot_config(self, key: str, value: str) -> None:
        await self._request("PUT", "/api/v1/bot/config", json={"key": key, "value": value})
        
    async def get_quotas(self) -> Dict[str, Any]:
        return await self._request("GET", "/api/v1/db/quotas")
        
    async def update_quota(self, membership_type: str, max_quota: Optional[int]) -> Dict[str, Any]:
        return await self._request("PUT", f"/api/v1/db/quotas/{membership_type}", json={"max_quota": max_quota})

    async def delete_bot_config(self, key: str) -> None:
        await self._request("DELETE", f"/api/v1/bot/config/{key}")

    async def get_paginated_players(self, page: int = 1, limit: int = 10, linked: str = "all") -> Dict[str, Any]:
        return await self._request("GET", f"/api/v1/db/players?page={page}&limit={limit}&linked={linked}")

    async def get_paginated_matches(self, page: int = 1, limit: int = 10) -> Dict[str, Any]:
        return await self._request("GET", f"/api/v1/db/matches?page={page}&limit={limit}")
        
    async def get_paginated_memberships(self, page: int = 1, limit: int = 10) -> Dict[str, Any]:
        return await self._request("GET", f"/api/v1/db/memberships?page={page}&limit={limit}")

    async def get_steam_player(self, steam_id: str) -> Optional[Dict[str, Any]]:
        try:
            return await self._request("GET", f"/api/v1/steam/player/{steam_id}")
        except Exception:
            return None
            
    async def get_steam_players_batch(self, steam_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        if not steam_ids:
            return {}
        try:
            return await self._request("GET", f"/api/v1/steam/players?steam_ids={','.join(steam_ids)}")
        except Exception:
            return {}
            
    async def get_player_historical_stats(self, steam_id: str) -> Optional[Dict[str, Any]]:
        try:
            return await self._request("GET", f"/api/v1/db/players/steam/{steam_id}/stats")
        except Exception:
            return None

    async def kick_player(self, steam_id: str, reason: str) -> None:
        await self._request("POST", f"/api/v1/players/{steam_id}/kick", json={"reason": reason})

    async def ban_player(self, steam_id: str, reason: str, duration_days: int = 0) -> None:
        await self._request("POST", f"/api/v1/players/{steam_id}/ban", json={"reason": reason, "duration_days": duration_days})
        
    async def unban_player(self, steam_id: str) -> None:
        await self._request("POST", f"/api/v1/players/{steam_id}/unban")

    async def switch_faction(self, steam_id: str, faction: str) -> None:
        await self._request("POST", f"/api/v1/players/{steam_id}/faction", json={"faction": faction})

    async def get_rcon_sync_status(self) -> Dict[str, Any]:
        return await self._request("GET", "/api/v1/db/rcon_sync_status")

    async def add_special_role(self, steam_id: str, role_id: str) -> None:
        await self._request("POST", f"/api/v1/db/players/{steam_id}/roles/{role_id}")

    async def get_latest_match(self) -> Optional[Dict[str, Any]]:
        try:
            return await self._request("GET", "/api/v1/db/matches/latest")
        except Exception:
            return None
