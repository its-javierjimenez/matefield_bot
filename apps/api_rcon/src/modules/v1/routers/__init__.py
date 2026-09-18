from src.modules.v1.routers.server import router as server_router
from src.modules.v1.routers.players import router as players_router
from src.modules.v1.routers.memberships import router as memberships_router
from src.modules.v1.routers.roles import router as roles_router
from src.modules.v1.routers.matches import router as matches_router
from src.modules.v1.routers.bans import router as bans_router
from src.modules.v1.routers.config import router as config_router

__all__ = [
    "server_router",
    "players_router",
    "memberships_router",
    "roles_router",
    "matches_router",
    "bans_router",
    "config_router",
]
