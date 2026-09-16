from .tasks_controller import ROUTER as TASKS_ROUTER
from .settings_controller import ROUTER as SETTINGS_ROUTER

ALL_CONTROLLERS = [
    TASKS_ROUTER,
    SETTINGS_ROUTER
]

__all__ = [
    "TASKS_ROUTER",
    "SETTINGS_ROUTER",
]