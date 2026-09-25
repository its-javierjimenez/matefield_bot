import aiohttp
import os
from typing import Dict, Any, Optional, List, Union

from wardogs_schemas import v1 as schemas

class APIClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.headers = {
            "X-API-Key": api_key,
            "Content-Type": "application/json"
        }
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(headers=self.headers)
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def _request(self, method: str, endpoint: str, **kwargs) -> Any:
        url = f"{self.base_url}{endpoint}"
        session = await self._get_session()
        async with session.request(method, url, **kwargs) as response:
            if response.status >= 400:
                detail = None
                try:
                    data = await response.json()
                    if isinstance(data, dict) and "detail" in data:
                        detail = data["detail"]
                except Exception:
                    pass
                if detail is None:
                    detail = await response.text()
                raise Exception(f"HTTP {response.status}: {detail}")
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
        req = schemas.LinkAccountRequest(discord_id=discord_id, steam_id=steam_id)
        await self._request("POST", "/api/v1/db/players/link", json=req.model_dump())

    async def unlink_account(self, discord_id: str) -> None:
        req = schemas.UnlinkAccountRequest(discord_id=discord_id)
        await self._request("POST", "/api/v1/db/players/unlink", json=req.model_dump())

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

    async def add_membership(self, steam_id: str, membership_type: str, days: Optional[int] = None, special_role: Optional[str] = None, special_role_id: Optional[int] = None, role_granted_id: Optional[int] = None, is_booster: bool = False, server_id: Optional[int] = None) -> None:
        req = schemas.AddMembershipRequest(
            steam_id=steam_id,
            membership_type=membership_type,
            days=days,
            special_role=special_role,
            special_role_id=special_role_id,
            role_granted_id=role_granted_id,
            is_booster=is_booster,
            server_id=server_id
        )
        await self._request("POST", "/api/v1/db/players/membership", json=req.model_dump(exclude_none=False))

    async def edit_membership(self, membership_id: int, days: Optional[int] = None, add_days: Optional[int] = None, membership_type: Optional[str] = None, is_active: Optional[bool] = None, is_booster: Optional[bool] = None, server_id: Optional[int] = None) -> None:
        kwargs: Dict[str, Any] = {
            "days": days,
            "add_days": add_days,
            "membership_type": membership_type,
            "is_active": is_active,
            "is_booster": is_booster,
        }
        if server_id is not None:
            kwargs["server_id"] = server_id
        req = schemas.EditMembershipRequest(**kwargs)
        await self._request("PUT", f"/api/v1/db/memberships/{membership_id}", json=req.model_dump(exclude_unset=True))

    async def compensate_memberships(self, days: int) -> Dict[str, Any]:
        req = schemas.CompensateRequest(days=days)
        return await self._request("POST", "/api/v1/db/memberships/compensate", json=req.model_dump())

    async def delete_membership(self, membership_id: int) -> None:
        await self._request("DELETE", f"/api/v1/db/memberships/{membership_id}")

    async def export_memberships(self) -> Dict[str, Any]:
        data = await self._request("POST", "/api/v1/db/memberships/export")
        return schemas.ExportMembershipsResponse.model_validate(data).model_dump()

    async def download_file_bytes(self, endpoint: str) -> bytes:
        url = f"{self.base_url}{endpoint}"
        session = await self._get_session()
        async with session.get(url) as response:
            response.raise_for_status()
            return await response.read()

    async def remove_special_role(self, steam_id: str, role_id: str) -> None:
        await self._request("DELETE", f"/api/v1/db/players/{steam_id}/roles/{role_id}")

    async def edit_player(self, steam_id: str, discord_id: Optional[str] = None, custom_welcome_message: Optional[str] = None, observations: Optional[str] = None) -> None:
        req = schemas.EditPlayerRequest(
            discord_id=discord_id,
            custom_welcome_message=custom_welcome_message,
            observations=observations
        )
        await self._request("PUT", f"/api/v1/db/players/{steam_id}", json=req.model_dump(exclude_unset=True))

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
        payload = schemas.SetBotConfigRequest(key=key, value=value).model_dump()
        await self._request("PUT", "/api/v1/bot/config", json=payload)
        
    async def get_quotas(self) -> Dict[str, Any]:
        return await self._request("GET", "/api/v1/db/quotas")
        
    async def update_quota(self, membership_type: str, max_quota: Optional[int]) -> Dict[str, Any]:
        payload = schemas.QuotaUpdateRequest(max_quota=max_quota).model_dump()
        return await self._request("PUT", f"/api/v1/db/quotas/{membership_type}", json=payload)

    async def delete_bot_config(self, key: str) -> None:
        await self._request("DELETE", f"/api/v1/bot/config/{key}")

    async def get_paginated_players(self, page: int = 1, limit: int = 10, linked: str = "all") -> Dict[str, Any]:
        return await self._request("GET", f"/api/v1/db/players?page={page}&limit={limit}&linked={linked}")

    async def get_paginated_matches(self, page: int = 1, limit: int = 10) -> Dict[str, Any]:
        return await self._request("GET", f"/api/v1/db/matches?page={page}&limit={limit}")
        
    async def get_paginated_memberships(self, page: int = 1, limit: int = 10, discord_id: Optional[str] = None) -> Dict[str, Any]:
        url = f"/api/v1/db/memberships?page={page}&limit={limit}"
        if discord_id:
            url += f"&discord_id={discord_id}"
        return await self._request("GET", url)

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
        payload = schemas.ReasonRequest(reason=reason).model_dump(exclude_none=True)
        await self._request("POST", f"/api/v1/players/{steam_id}/kick", json=payload)

    async def ban_player(self, steam_id: str, reason: str, duration_days: int = 0, solo_discord: bool = False) -> None:
        payload = schemas.ReasonRequest(reason=reason, duration_days=duration_days, solo_discord=solo_discord).model_dump(exclude_none=True)
        await self._request("POST", f"/api/v1/players/{steam_id}/ban", json=payload)
        
    async def unban_player(self, steam_id: str) -> None:
        await self._request("POST", f"/api/v1/players/{steam_id}/unban")

    async def sync_bans(self) -> Dict[str, Any]:
        return await self._request("POST", "/api/v1/db/sync_bans")

    async def switch_faction(self, steam_id: str, faction: str) -> None:
        payload = schemas.FactionRequest(faction=faction).model_dump()
        await self._request("POST", f"/api/v1/players/{steam_id}/faction", json=payload)

    async def get_rcon_sync_status(self) -> Dict[str, Any]:
        return await self._request("GET", "/api/v1/db/rcon_sync_status")

    async def add_special_role(self, steam_id: str, role_id: str) -> None:
        await self._request("POST", f"/api/v1/db/players/{steam_id}/roles/{role_id}")

    async def get_latest_match(self) -> Optional[Dict[str, Any]]:
        try:
            return await self._request("GET", "/api/v1/db/matches/latest")
        except Exception:
            return None

    async def get_all_roles(self) -> List[Dict[str, Any]]:
        try:
            return await self._request("GET", "/api/v1/db/roles")
        except Exception:
            return []

    async def register_role(self, code: str, name: str, role_type: str, discord_role_id: str) -> None:
        payload = schemas.RoleRegisterRequest(
            code=code,
            name=name,
            role_type=role_type,
            discord_role_id=discord_role_id
        ).model_dump()
        await self._request("POST", "/api/v1/db/roles", json=payload)

    # RCON Server management endpoints
    async def get_rcon_servers(self) -> List[Dict[str, Any]]:
        return await self._request("GET", "/api/v1/rcon-servers")

    async def create_rcon_server(
        self,
        ip: str,
        port: int,
        password: str,
        name: Optional[str] = None,
        scheme: str = "http",
        is_active: bool = True,
        is_default: bool = False
    ) -> Dict[str, Any]:
        req = schemas.CreateRconServerRequest(
            ip=ip,
            port=port,
            password=password,
            name=name,
            scheme=scheme,
            is_active=is_active,
            is_default=is_default
        )
        return await self._request("POST", "/api/v1/rcon-servers", json=req.model_dump(exclude_none=True))

    async def get_rcon_server(self, server_id: int) -> Dict[str, Any]:
        return await self._request("GET", f"/api/v1/rcon-servers/{server_id}")

    async def update_rcon_server(self, server_id: int, **kwargs) -> Dict[str, Any]:
        req = schemas.UpdateRconServerRequest(**kwargs)
        return await self._request("PUT", f"/api/v1/rcon-servers/{server_id}", json=req.model_dump(exclude_unset=True))

    async def delete_rcon_server(self, server_id: int) -> Dict[str, Any]:
        return await self._request("DELETE", f"/api/v1/rcon-servers/{server_id}")

    async def test_rcon_server(self, server_id: int) -> Dict[str, Any]:
        return await self._request("POST", f"/api/v1/rcon-servers/{server_id}/test")

    async def sync_all_rcon_servers(self) -> Dict[str, Any]:
        return await self._request("POST", "/api/v1/rcon-servers/sync-all")

    # Membership Types management endpoints
    async def get_membership_types(self, active_only: bool = False) -> List[Dict[str, Any]]:
        return await self._request("GET", f"/api/v1/membership-types?active_only={active_only}")

    async def get_membership_type(self, identifier: Union[int, str]) -> Dict[str, Any]:
        return await self._request("GET", f"/api/v1/membership-types/{identifier}")

    async def create_membership_type(self, **kwargs) -> Dict[str, Any]:
        req = schemas.CreateMembershipTypeRequest(**kwargs)
        return await self._request("POST", "/api/v1/membership-types", json=req.model_dump(exclude_none=True))

    async def update_membership_type(self, type_id: int, **kwargs) -> Dict[str, Any]:
        req = schemas.UpdateMembershipTypeRequest(**kwargs)
        return await self._request("PUT", f"/api/v1/membership-types/{type_id}", json=req.model_dump(exclude_unset=True))

    async def delete_membership_type(self, type_id: int) -> Dict[str, Any]:
        return await self._request("DELETE", f"/api/v1/membership-types/{type_id}")


