import typing
import datetime
import pydantic
import pydantic_mongo


class LoggingSchema(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(
        extra="allow",
        validate_by_alias=True,
        validate_by_name=True,
        serialize_by_alias=True,
    )

    id: typing.Optional[pydantic_mongo.PydanticObjectId] = pydantic.Field(
        default=None,
        description="The unique identifier for the logging entry",
    )


    receivedArtifact: str = pydantic.Field(
        description="The artifact that received the logged event",
        examples=[
            "MAKER", "EXPORT", "DECORATOR", "CARONTE", "API"
        ]
    )

    senderArtifact: typing.Optional[str] = pydantic.Field(
        default=None,
        description="The artifact that sent the logged event",
        examples=[
            "MAKER", "EXPORT", "DECORATOR", "CARONTE", "API"
        ]
    )

    timestamp: int = pydantic.Field(
        description="Unix timestamp of the logged event",
        examples=[1625247600]
    )

    eventType : str = pydantic.Field(
        description="Type of the logged event",
        examples=[
            "CREATED" , "PENDING", "EXPORTED", "COMPLETED", "ERROR", "REVIEW", "CRITICAL"
        ]
    )

    eventMessage: str = pydantic.Field(
        description="Detailed message about the logged event",
        examples=[
            "Task created successfully", "Audio export completed", "Critical error in processing"
        ]
    )

    userEmail: typing.Optional[str] = pydantic.Field(
        default=None,
        description="Email associated with the task/event, when available",
        examples=["user@example.com"],
    )

    userLanguage: typing.Optional[str] = pydantic.Field(
        default=None,
        description="Language associated with the task/event, when available",
        examples=["es", "en"],
    )

    userLevel: typing.Optional[int] = pydantic.Field(
        default=None,
        description="User level associated with the task/event, when available",
        ge=0,
        examples=[1, 2, 3],
    )

    queueRoutingKey: typing.Optional[str] = pydantic.Field(
        default=None,
        description="The routing key of the queue from which the log was received",
        examples=[
            "maker.normal.tasks", "export.priority.tasks", "decorator.normal.tasks"
        ]
    )

    additionalInfo: dict = pydantic.Field(
        description="Additional information related to the logged event",
        default_factory=dict
    )

    audioRequestID: str = pydantic.Field(
        description="The ID of the audio request associated with the logged event",
        examples=["A91834aWSdjnalawnlz"]
    )


class LoggingCreateResponse(pydantic.BaseModel):
    message: str = pydantic.Field(
        description="Human readable status about the logging operation",
        examples=["Logging event stored."]
    )
    event: LoggingSchema = pydantic.Field(
        description="The logging event that was stored"
    )


class LoggingEventsResponse(pydantic.BaseModel):
    items: typing.List[LoggingSchema] = pydantic.Field(
        default_factory=list,
        description="Collection of logging events matching the provided filters"
    )


class loggingEventSummaryUserData(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(
        extra="ignore",
        validate_by_alias=True,
        validate_by_name=True,
        serialize_by_alias=True,
    )

    userEmail: str = pydantic.Field(
        description="Email of the user",
        examples=["user@example.com"]
    )

class UserEventSummary(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(
        extra="ignore",
        validate_by_alias=True,
        validate_by_name=True,
        serialize_by_alias=True,
    )

    userData: loggingEventSummaryUserData = pydantic.Field(
        ...,
        description="Minimal user identity payload (e.g. { 'userEmail': 'aaa' }).",
    )

    events: dict = pydantic.Field(
        default_factory=dict,
        description="Mapping of eventType -> occurrence count",
    )

    fromDate: int = pydantic.Field(..., description="Start timestamp (unix seconds)")
    toDate: int = pydantic.Field(..., description="End timestamp (unix seconds)")


class LoggingWebhookBase(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(
        extra="forbid",
        validate_by_alias=True,
        validate_by_name=True,
        serialize_by_alias=True,
    )

    serviceName: str = pydantic.Field(
        description="Nombre del servicio que recibe el webhook",
        min_length=3,
        max_length=128,
    )
    
    targetUrl: str = pydantic.Field(
        description="URL a la que se notificará con el payload LoggingSchema",
        examples=["https://example.com/hooks/logging"],
    )

    description: typing.Optional[str] = pydantic.Field(
        default=None,
        description="Descripción opcional del servicio suscrito",
        max_length=256,
    )

    isActive: bool = pydantic.Field(
        default=True,
        description="Indica si el webhook está activo para recibir eventos",
    )


class LoggingWebhookSchema(LoggingWebhookBase):
    id: typing.Optional[pydantic_mongo.PydanticObjectId] = pydantic.Field(
        default=None,
        description="Identificador del webhook registrado",
    )
    createdAt: datetime.datetime = pydantic.Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        description="Fecha de creación del registro",
    )
    updatedAt: datetime.datetime = pydantic.Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        description="Fecha de última actualización del registro",
    )


class LoggingWebhookCreateRequest(LoggingWebhookBase):
    pass


class LoggingWebhookRegistrationResponse(pydantic.BaseModel):
    message: str = pydantic.Field(
        description="Mensaje de confirmación",
        examples=["Webhook registrado correctamente."],
    )
    webhook: LoggingWebhookSchema = pydantic.Field(
        description="Webhook registrado",
    )