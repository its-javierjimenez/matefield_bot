"""
Configuration module for api_rcon, powered by the centralized wardogs_config package.
"""
from wardogs_config import (
    ENVIRONMENT_SETTINGS,
    EnvironmentSettings,
    SecuritySettings,
    ConnectionSettings,
    DiscordBotSettings,
    BOT_SETTINGS,
    is_prod,
)

__all__ = [
    "ENVIRONMENT_SETTINGS",
    "EnvironmentSettings",
    "SecuritySettings",
    "ConnectionSettings",
    "DiscordBotSettings",
    "BOT_SETTINGS",
    "is_prod",
]
