import faststream.rabbit.fastapi as faststream_rabbit_fastapi
from .controllers import ALL_CONTROLLERS

ROUTER = faststream_rabbit_fastapi.RabbitRouter(
    prefix="/caronte",
    tags=["caronte"]
)

for controller in ALL_CONTROLLERS:
    ROUTER.include_router(controller)