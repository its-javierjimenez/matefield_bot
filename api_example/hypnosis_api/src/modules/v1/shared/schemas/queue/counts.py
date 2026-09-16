"""Pydantic models describing RabbitMQ queue counters."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class QueueCount(BaseModel):
    """Messages counts for a specific RabbitMQ queue."""

    model_config = ConfigDict(
        extra="ignore",
        populate_by_name=True,
        validate_assignment=True,
        validate_default=True,
        serialize_by_alias=True,
    )

    queueName: str = Field(..., description="Queue friendly name used internally.")
    rabbitQueue: str = Field(..., description="Exact RabbitMQ queue name.")
    messages: int = Field(0, description="Total messages in queue (ready + unacknowledged).", ge=0)
    messagesReady: int = Field(0, description="Messages ready to be delivered.", ge=0)
    messagesUnacknowledged: int = Field(0, description="Messages delivered but not yet acknowledged.", ge=0)


class RemainingTasksResponse(BaseModel):
    """Aggregated remaining tasks per artifact."""

    model_config = ConfigDict(
        extra="ignore",
        populate_by_name=True,
        validate_assignment=True,
        validate_default=True,
        serialize_by_alias=True,
    )

    artifact: str = Field(..., description="Artifact identifier (MAKER, EXPORT, DECORATOR, ...).")
    total: int = Field(0, description="Total pending tasks across queues.", ge=0)
    queues: dict[str, QueueCount] = Field(default_factory=dict, description="Breakdown per logical queue key.")
