import fastapi
import sentry_sdk
from guard.middleware import SecurityMiddleware
from guard.models import SecurityConfig

from .config import ENVIRONMENT_SETTINGS
from .modules import V1_ROUTER
from .security.guard import verify_api_key_guard

sentry_sdk.init(
    dsn=ENVIRONMENT_SETTINGS.SENTRY_SETTINGS.SENTRY_DSN,
    send_default_pii=True,
    traces_sample_rate=ENVIRONMENT_SETTINGS.SENTRY_SETTINGS.SENTRY_SAMPLE_RATE,
    environment=ENVIRONMENT_SETTINGS.SENTRY_SETTINGS.SENTRY_ENVIRONMENT,
    release=ENVIRONMENT_SETTINGS.SENTRY_SETTINGS.SENTRY_RELEASE,
    enable_logs=ENVIRONMENT_SETTINGS.SENTRY_SETTINGS.SENTRY_ENABLE_LOGS
)

APP = fastapi.FastAPI(
    title="HYPNOSIS API" + " - " + ENVIRONMENT_SETTINGS.SENTRY_SETTINGS.SENTRY_ENVIRONMENT,
    version=ENVIRONMENT_SETTINGS.SENTRY_SETTINGS.SENTRY_RELEASE,
    description="A FastAPI application for hypnosis pipeline",
)

security_config = SecurityConfig(
    custom_request_check=verify_api_key_guard,
    enable_penetration_detection=False,
    enable_rate_limiting=False,
    enable_agent=False,
    enable_ip_banning=False,
)

APP.add_middleware(SecurityMiddleware, config=security_config)

APP.include_router(V1_ROUTER)