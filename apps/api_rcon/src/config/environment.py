"""
Environment settings re-exported from centralized wardogs_config package.
"""
from wardogs_config.environment import (
    EnvironmentSettings,
    ENVIRONMENT_SETTINGS,
    is_prod,
)

__all__ = ["EnvironmentSettings", "ENVIRONMENT_SETTINGS", "is_prod"]
