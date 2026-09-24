from typing import Optional, List
from sqlmodel import Field, Session, SQLModel, create_engine, Relationship
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, BigInteger, ForeignKey, Text
import uuid

from src.config import ENVIRONMENT_SETTINGS

from enum import Enum

class RoleType(str, Enum):
    SYSTEM = "SYSTEM"
    VIP = "VIP"
    PUNISHMENT = "PUNISHMENT"
    PUBLIC = "PUBLIC"
    SPECIAL = "SPECIAL"

# --- Intermediary Tables ---

class PlayerRole(SQLModel, table=True):
    __tablename__ = "player_roles"
    steam_id: str = Field(foreign_key="players.steam_id", primary_key=True)
    role_id: int = Field(sa_column=Column(BigInteger(), ForeignKey("roles.id"), primary_key=True))

# --- Core Entities ---

class Role(SQLModel, table=True):
    __tablename__ = "roles"
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(unique=True, index=True)
    name: str
    discord_role_id: Optional[str] = Field(default=None, index=True)
    role_type: str = Field(index=True)
    
    # Relationships
    players: List["Player"] = Relationship(back_populates="roles", link_model=PlayerRole)


class Player(SQLModel, table=True):
    __tablename__ = "players"
    steam_id: str = Field(primary_key=True)
    discord_id: Optional[str] = Field(default=None, unique=True, index=True)
    custom_welcome_message: Optional[str] = Field(default=None)
    observations: Optional[str] = Field(default=None)
    in_game_name: Optional[str] = Field(default=None)
    avatar_url: Optional[str] = Field(default=None)
    
    # Relationships
    roles: List[Role] = Relationship(back_populates="players", link_model=PlayerRole)
    memberships: List["Membership"] = Relationship(back_populates="player")
    match_stats: List["MatchPlayerStats"] = Relationship(back_populates="player")


class Membership(SQLModel, table=True):
    __tablename__ = "memberships"
    id: Optional[int] = Field(default=None, primary_key=True)
    steam_id: str = Field(foreign_key="players.steam_id", index=True)
    membership_type: str = Field(index=True, sa_column_kwargs={"name": "type"})
    start_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column("start_date", DateTime(timezone=True)))
    end_time: Optional[datetime] = Field(default=None, sa_column=Column("end_date", DateTime(timezone=True))) # Null means permanent
    is_active: bool = Field(default=True)
    is_booster: bool = Field(default=False)
    special_role_id: Optional[int] = Field(default=None, sa_column=Column("role_granted_id", BigInteger(), ForeignKey("roles.id")))
    rcon_sync_status: str = Field(default="PENDING", sa_column_kwargs={"server_default": "PENDING"}) # PENDING, SUCCESS, FAILED
    server_id: Optional[int] = Field(default=None, foreign_key="rcon_servers.id")
    tebex_transaction_id: Optional[str] = Field(default=None, index=True)
    tebex_subscription_id: Optional[str] = Field(default=None, index=True)
    payment_source: str = Field(default="MANUAL", sa_column_kwargs={"server_default": "MANUAL"}) # MANUAL, TEBEX
    
    # Relationships
    player: Player = Relationship(back_populates="memberships")

class PlayerSession(SQLModel, table=True):
    __tablename__ = "player_sessions"
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    steam_id: str = Field(foreign_key="players.steam_id", index=True)
    
    start_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True)))
    end_time: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    
    total_seconds: int = Field(default=0)
    seeding_seconds: int = Field(default=0)

class Ban(SQLModel, table=True):
    __tablename__ = "bans"
    id: Optional[int] = Field(default=None, primary_key=True)
    steam_id: str = Field(foreign_key="players.steam_id", index=True)
    reason: str
    is_active: bool = Field(default=True)
    rcon_sync_status: str = Field(default="PENDING")
    banned_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True)))
    expires_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True)))

class Team(SQLModel, table=True):
    __tablename__ = "teams"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True) # Lonestar, Manticore, Valkyre
    code: str = Field(unique=True) # BLU, GRN, RED


class Match(SQLModel, table=True):
    __tablename__ = "matches"
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    map_name: str
    start_time: datetime = Field(sa_column=Column(DateTime(timezone=True)))
    end_time: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    winning_team_id: Optional[int] = Field(default=None, foreign_key="teams.id")
    
    # Relationships
    team_stats: List["MatchTeamStats"] = Relationship(back_populates="match")
    player_stats: List["MatchPlayerStats"] = Relationship(back_populates="match")


# --- Stats Tables ---

class MatchTeamStats(SQLModel, table=True):
    __tablename__ = "match_team_stats"
    match_id: str = Field(foreign_key="matches.id", primary_key=True)
    team_id: int = Field(foreign_key="teams.id", primary_key=True)
    score: int = Field(default=0)
    
    # Relationships
    match: Match = Relationship(back_populates="team_stats")
    team: Team = Relationship()


class MatchPlayerStats(SQLModel, table=True):
    __tablename__ = "match_player_stats"
    steam_id: str = Field(foreign_key="players.steam_id", primary_key=True)
    match_id: str = Field(foreign_key="matches.id", primary_key=True)
    team_id: Optional[int] = Field(default=None, foreign_key="teams.id")
    kills: int = Field(default=0)
    deaths: int = Field(default=0)
    cash_earned: int = Field(default=0)
    
    # Relationships
    match: Match = Relationship(back_populates="player_stats")
    player: Player = Relationship(back_populates="match_stats")
    team: Optional[Team] = Relationship()


class BotConfig(SQLModel, table=True):
    __tablename__ = "bot_config"
    config_key: str = Field(primary_key=True)
    config_value: str


class MembershipTypeConfig(SQLModel, table=True):
    __tablename__ = "membership_type_configs"
    membership_type: str = Field(primary_key=True)
    max_quota: Optional[int] = Field(default=None) # Null = infinite


class MembershipType(SQLModel, table=True):
    __tablename__ = "membership_types"
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(unique=True, index=True)
    name: str
    description: Optional[str] = Field(default=None)
    price_usd: float = Field(default=0.0)
    billing_type: str = Field(default="ONE_TIME") # "ONE_TIME" or "RECURRING"
    default_days: int = Field(default=30)         # 0 = permanente
    max_quota: Optional[int] = Field(default=None)# None = ilimitado
    discord_role_id: Optional[str] = Field(default=None)
    server_id: Optional[int] = Field(default=None, foreign_key="rcon_servers.id")
    is_active: bool = Field(default=True)
    tebex_package_id: Optional[int] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True), nullable=False))


class PaymentRecord(SQLModel, table=True):
    __tablename__ = "payment_records"
    id: Optional[int] = Field(default=None, primary_key=True)
    transaction_id: str = Field(unique=True, index=True)
    event_type: str = Field(index=True) # payment.completed, recurring-payment.renewed, etc.
    steam_id: Optional[str] = Field(default=None, index=True)
    discord_id: Optional[str] = Field(default=None, index=True)
    package_id: Optional[int] = Field(default=None, index=True)
    package_name: Optional[str] = Field(default=None)
    amount: float = Field(default=0.0)
    currency: str = Field(default="USD")
    status: str = Field(default="COMPLETED", index=True) # COMPLETED, RENEWED, CANCELLED, REFUNDED, IGNORED
    raw_payload: str = Field(default="{}", sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True), nullable=False))


class RconServer(SQLModel, table=True):
    __tablename__ = "rcon_servers"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    ip: str
    port: int
    password: str
    scheme: str = Field(default="http") # "http" or "https"
    is_active: bool = Field(default=True)
    is_default: bool = Field(default=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True), nullable=False))

    @property
    def base_url(self) -> str:
        return f"{self.scheme}://{self.ip}:{self.port}"


from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine

# --- Database Setup ---
engine = create_async_engine(ENVIRONMENT_SETTINGS.CONNECTIONS_SETTINGS.DATABASE_URL, echo=False)

async def get_session():
    async with AsyncSession(engine) as session:
        yield session

