from .settings_controller import ROUTER as SETTINGS_ROUTER
from .tasks_controller import ROUTER as TASKS_ROUTER
from .templates_controller import ROUTER as TEMPLATES_ROUTER
from .audios_controller import ROUTER as AUDIOS_ROUTER

ALL_CONTROLLERS = [
    SETTINGS_ROUTER,
    TASKS_ROUTER,
    TEMPLATES_ROUTER,
    AUDIOS_ROUTER
]

__all__ = ["SETTINGS_ROUTER", "TASKS_ROUTER", "TEMPLATES_ROUTER", "AUDIOS_ROUTER"]