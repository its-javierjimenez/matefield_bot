from pydantic import BaseModel
from typing import Optional, List, Any, Dict
from datetime import datetime

class ConfigUpdateRequest(BaseModel):
    revision: str
    new_text: str

class LinkAccountRequest(BaseModel):
    discord_id: str
    steam_id: str

class UnlinkAccountRequest(BaseModel):
    discord_id: str

class EditPlayerRequest(BaseModel):
    discord_id: Optional[str] = None
    custom_welcome_message: Optional[str] = None
    observations: Optional[str] = None

class AddMembershipRequest(BaseModel):
    steam_id: str
    membership_type: str
    days: Optional[int] = None
    special_role: Optional[str] = None

class EditMembershipRequest(BaseModel):
    days: Optional[int] = None
    add_days: Optional[int] = None
    membership_type: Optional[str] = None
    is_active: Optional[bool] = None

class CompensateRequest(BaseModel):
    days: int

class SetBotConfigRequest(BaseModel):
    key: str
    value: str

class QuotaUpdateRequest(BaseModel):
    max_quota: Optional[int]

class RoleRegisterRequest(BaseModel):
    code: str
    name: str
    role_type: str
    discord_role_id: Optional[str] = None

class PlayerBanRequest(BaseModel):
    steam_id: str
    reason: str
    banned_by: str
    duration_days: Optional[int] = None

class UnbanRequest(BaseModel):
    steam_id: str
    reason: str
