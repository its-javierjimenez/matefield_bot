import aiohttp
import time
import asyncio
from typing import Any

from wardogs_schemas import v1 as schemas
from src.config import ENVIRONMENT_SETTINGS

class RCONClient:
    def __init__(self, base_url: str, password: str):
        self.base_url = base_url.rstrip('/')
        self.password = password
        self.headers = {
            "Authorization": f"Bearer {self.password}",
            "Content-Type": "application/json"
        }
        self._cache = {}
        self._cache_lock = asyncio.Lock()
        self._cache_ttl = 3.0

    async def _get_cached(self, key: str, fetcher_coro) -> Any:
        async with self._cache_lock:
            now = time.time()
            if key in self._cache:
                timestamp, data = self._cache[key]
                if now - timestamp < self._cache_ttl:
                    return data
            # Fetch new data
            data = await fetcher_coro()
            # Update cache timestamp AFTER fetch succeeds
            self._cache[key] = (time.time(), data)
            return data

    async def _request(self, method: str, endpoint: str, **kwargs) -> Any:
        url = f"{self.base_url}{endpoint}"
        
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(headers=self.headers, connector=connector) as session:
            async with session.request(method, url, **kwargs) as response:
                if response.status >= 400:
                    err_body = await response.text()
                    raise aiohttp.ClientResponseError(
                        response.request_info,
                        response.history,
                        status=response.status,
                        message=f"{response.reason}: {err_body}",
                        headers=response.headers
                    )
                if "application/json" in response.headers.get("Content-Type", ""):
                    return await response.json()
                return await response.text()

    async def get_status(self) -> schemas.Status:
        async def fetch():
            data = await self._request("GET", "/v1/status")
            return schemas.Status.model_validate(data)
        return await self._get_cached("status", fetch)

    async def get_players(self) -> schemas.Players1:
        async def fetch():
            data = await self._request("GET", "/v1/players")
            return schemas.Players1.model_validate(data)
        return await self._get_cached("players", fetch)


    async def get_audit_logs(self, limit: int = 50) -> schemas.Audit:
        data = await self._request("GET", f"/v1/audit?limit={limit}")
        return schemas.Audit.model_validate(data)

    async def get_reserved_slots(self) -> schemas.ReservedSlots:
        data = await self._request("GET", "/v1/reserved-slots")
        return schemas.ReservedSlots.model_validate(data)

    async def sync_reserved_slots(self, steam_ids: list[str]) -> None:
        config = await self.get_config()
        text = config.text or ""
        revision = config.revision or ""
        lines = text.split('\n')
        
        new_lines = []
        for line in lines:
            if 'DefaultReservedPlayerIds' not in line:
                new_lines.append(line)
                
        insert_idx = -1
        for i, line in enumerate(new_lines):
            if line.strip() == '[/Script/WDGame.WDGameSession]':
                insert_idx = i
                break
                
        if insert_idx == -1:
            new_lines.append('')
            new_lines.append('[/Script/WDGame.WDGameSession]')
            insert_idx = len(new_lines) - 1
            
        if insert_idx == -1:
            new_lines.append('')
            new_lines.append('[/Script/WDGame.WDGameSession]')
            insert_idx = len(new_lines) - 1
            
        if insert_idx != -1:
            slot_lines = ['!DefaultReservedPlayerIds=ClearArray']
            for sid in steam_ids:
                slot_lines.append(f'.DefaultReservedPlayerIds={sid}')
            new_lines = new_lines[:insert_idx+1] + slot_lines + new_lines[insert_idx+1:]
            new_text = '\n'.join(new_lines)
            await self.update_config(revision, new_text)

    async def get_bans(self) -> list[str]:
        config = await self.get_config()
        text = config.text or ""
        lines = text.split('\n')
        bans = []
        for line in lines:
            line = line.strip()
            if line.startswith('.DefaultBannedPlayerIds='):
                val = line.split('=', 1)[1].strip()
                if val:
                    bans.append(val)
            elif line.startswith('+DefaultBannedPlayerIds='):
                val = line.split('=', 1)[1].strip()
                if val:
                    bans.append(val)
        return bans

    async def sync_banned_slots(self, steam_ids: list[str]) -> None:
        config = await self.get_config()
        text = config.text or ""
        revision = config.revision or ""
        lines = text.split('\n')
        
        new_lines = []
        for line in lines:
            if 'DefaultBannedPlayerIds' not in line:
                new_lines.append(line)
                
        insert_idx = -1
        for i, line in enumerate(new_lines):
            if line.strip() == '[/Script/WDGame.WDGameSession]':
                insert_idx = i
                break
                
        if insert_idx == -1:
            new_lines.append('')
            new_lines.append('[/Script/WDGame.WDGameSession]')
            insert_idx = len(new_lines) - 1
            
        if insert_idx == -1:
            new_lines.append('')
            new_lines.append('[/Script/WDGame.WDGameSession]')
            insert_idx = len(new_lines) - 1
            
        if insert_idx != -1:
            slot_lines = ['!DefaultBannedPlayerIds=ClearArray']
            for sid in steam_ids:
                slot_lines.append(f'.DefaultBannedPlayerIds={sid}')
            new_lines = new_lines[:insert_idx+1] + slot_lines + new_lines[insert_idx+1:]
            new_text = '\n'.join(new_lines)
            await self.update_config(revision, new_text)

    async def broadcast(self, message: str) -> None:
        await self._request("POST", "/v1/broadcast", json={"message": message})

    async def send_player_message(self, steam_id: str, message: str) -> None:
        await self._request("POST", f"/v1/players/{steam_id}/message", json={"message": message})

    async def get_config(self) -> schemas.Config1:
        async with aiohttp.ClientSession(headers=self.headers) as session:
            async with session.get(f"{self.base_url}/v1/config") as response:
                response.raise_for_status()
                data = await response.json()
                return schemas.Config1.model_validate(data)
    async def update_config(self, revision: str, new_text: str) -> schemas.ConfigResult:
        headers = self.headers.copy()
        headers["If-Match"] = f'"{revision}"'
        headers["Content-Type"] = "text/plain"
        
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.put(f"{self.base_url}/v1/config?force=true&fullApply=true", data=new_text) as response:
                response.raise_for_status()
                data = await response.json()
                return schemas.ConfigResult.model_validate(data)
        
    async def broadcast(self, message: str) -> None:
        payload = {"message": message}
        await self._request("POST", "/v1/broadcast", json=payload)

    async def send_player_message(self, steam_id: str, message: str) -> None:
        payload = {"message": message}
        await self._request("POST", f"/v1/players/{steam_id}/message", json=payload)

    async def kick_player(self, steam_id: str, reason: str) -> None:
        payload = {"reason": reason}
        await self._request("POST", f"/v1/players/{steam_id}/kick", json=payload)

    async def ban_player(self, steam_id: str, reason: str) -> None:
        payload = {"steamId": steam_id, "reason": reason}
        await self._request("POST", "/v1/bans", json=payload)

    async def switch_faction(self, steam_id: str, faction: str) -> None:
        payload = {"faction": faction}
        await self._request("PATCH", f"/v1/players/{steam_id}", json=payload)

    async def set_team_balancing(self, enabled: bool, threshold: int = 1) -> None:
        config = await self.get_config()
        text = config.text or ""
        revision = config.revision or ""
        lines = text.split('\n')
        
        target_section = "[/Script/WDGame.WDGameStateSession]"
        lock_val = "true" if enabled else "false"
        thresh_val = str(threshold)
        
        new_lines = []
        section_idx = -1
        in_target_section = False
        has_lock = False
        has_thresh = False
        
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('[') and stripped.endswith(']'):
                in_target_section = (stripped.lower() == target_section.lower())
                if in_target_section:
                    section_idx = len(new_lines)
                new_lines.append(line)
                continue
                
            if in_target_section:
                if stripped.startswith('bLockOverpopulatedTeamsConfig'):
                    new_lines.append(f"bLockOverpopulatedTeamsConfig={lock_val}")
                    has_lock = True
                    continue
                elif stripped.startswith('OverpopulatedTeamThresholdConfig'):
                    new_lines.append(f"OverpopulatedTeamThresholdConfig={thresh_val}")
                    has_thresh = True
                    continue
            new_lines.append(line)
            
        if section_idx == -1:
            new_lines.append("")
            new_lines.append(target_section)
            new_lines.append(f"bLockOverpopulatedTeamsConfig={lock_val}")
            new_lines.append(f"OverpopulatedTeamThresholdConfig={thresh_val}")
        else:
            insertions = []
            if not has_thresh:
                insertions.append(f"OverpopulatedTeamThresholdConfig={thresh_val}")
            if not has_lock:
                insertions.append(f"bLockOverpopulatedTeamsConfig={lock_val}")
            for ins in insertions:
                new_lines.insert(section_idx + 1, ins)
                    
        new_text = '\n'.join(new_lines)
        await self.update_config(revision, new_text)

# Instance to be imported by the router
rcon_client = RCONClient(
    base_url=ENVIRONMENT_SETTINGS.CONNECTIONS_SETTINGS.RCON_URL,
    password=ENVIRONMENT_SETTINGS.CONNECTIONS_SETTINGS.RCON_PASSWORD
)

