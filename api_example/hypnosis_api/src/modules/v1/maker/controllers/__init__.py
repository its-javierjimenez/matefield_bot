from .settings_controller import ROUTER as SETTINGS_ROUTER
from .static_controller import ROUTER as STATIC_ROUTER
from .tasks_controller import ROUTER as TASKS_ROUTER
from .comparator_controller import ROUTER as COMPARATOR_ROUTER
from .zips_controller import ROUTER as ZIPS_ROUTER


ALL_CONTROLLERS = [
    COMPARATOR_ROUTER,
    SETTINGS_ROUTER,
    STATIC_ROUTER,
    TASKS_ROUTER,
    ZIPS_ROUTER
]
__all__ = ["SETTINGS_ROUTER", "STATIC_ROUTER", "TASKS_ROUTER", "COMPARATOR_ROUTER", "ZIPS_ROUTER"]