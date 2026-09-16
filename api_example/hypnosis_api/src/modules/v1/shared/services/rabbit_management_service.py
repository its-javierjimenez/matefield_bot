"""Utilities to query RabbitMQ management API for queue statistics."""

from __future__ import annotations

import asyncio
import typing
from urllib.parse import quote

import httpx

from hypnosis_utils.logger import getLogger
from src.config import ENVIRONMENT_SETTINGS
from src.modules.v1.shared.schemas.queue import QueueCount, RemainingTasksResponse
from src.modules.v1.shared.connections.apis.rabbit_management_api import RABBIT_MANAGEMENT_CLIENT


LOGGER = getLogger("v1.shared.services.rabbit_management")

RABBIT_SETTINGS = ENVIRONMENT_SETTINGS.RABBIT_SETTINGS

class RabbitManagementError(Exception):
    """Raised when RabbitMQ management API cannot be queried successfully."""


async def fetchQueueCount(
    label: str,
    queueName: str,
    vhostEncoded: str,
) -> QueueCount:
    queueEncoded = quote(queueName, safe="")
    try:
        response = await RABBIT_MANAGEMENT_CLIENT.get(
            url=f"/queues/{vhostEncoded}/{queueEncoded}",
        )
    except httpx.RequestError as exc:  # pragma: no cover - network failure
        LOGGER.error(
            "[RABBIT] Failed to query management API",
            extra={"queueName": queueName, "error": str(exc)},
        )
        raise RabbitManagementError("Unable to communicate with RabbitMQ management API") from exc

    if response.status_code == 404:
        LOGGER.warning(
            "[RABBIT] Queue not found in management API",
            extra={"queueName": queueName, "label": label},
        )
        return QueueCount(
            queueName=label,
            rabbitQueue=queueName,
        )

    if not response.is_success:
        message = (
            f"Unexpected response querying queue {queueName}: "
            f"{response.status_code} {response.text}"
        )
        LOGGER.error("[RABBIT] %s", message)
        raise RabbitManagementError(message)

    payload: typing.Dict[str, typing.Any] = response.json()

    messagesTotal = int(payload.get("messages", 0) or 0)
    messagesReady = int(payload.get("messages_ready", 0) or 0)
    messagesUnacked = int(payload.get("messages_unacknowledged", 0) or 0)

    return QueueCount(
        queueName=label,
        rabbitQueue=payload.get("name", queueName),
        messages=messagesTotal,
        messagesReady=messagesReady,
        messagesUnacknowledged=messagesUnacked,
    )


async def getArtifactRemaining(
    artifact: str,
    queues: dict[str, str],
) -> RemainingTasksResponse:
    """Return remaining tasks for the given artifact across its queues."""

    if not queues:
        return RemainingTasksResponse(artifact=artifact, total=0, queues={})

    vhostEncoded = quote(RABBIT_SETTINGS.RABBIT_MANAGEMENT_VHOST, safe="")

    tasks = [
        fetchQueueCount(
            label=label,
            queueName=queueName,
            vhostEncoded=vhostEncoded,
        )
        for label, queueName in queues.items()
    ]
    queueCounts = await asyncio.gather(*tasks)

    total = sum(item.messages for item in queueCounts)
    queuesMap = {label: count for label, count in zip(queues.keys(), queueCounts)}

    return RemainingTasksResponse(
        artifact=artifact,
        total=total,
        queues=queuesMap,
    )
