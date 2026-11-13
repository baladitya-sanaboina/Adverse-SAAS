from dataclasses import dataclass

from app.core.settings import settings


@dataclass(frozen=True)
class PublicConfiguration:
    status: str
    app_name: str
    app_version: str
    environment: str
    api_prefix: str
    log_level: str
    storage_provider: str
    cors_origins: list[str]
    swagger_enabled: bool
    health_check_enabled: bool


def get_public_configuration() -> PublicConfiguration:
    return PublicConfiguration(
        status="loaded",
        app_name=settings.app_name,
        app_version=settings.app_version,
        environment=settings.environment,
        api_prefix=settings.api_prefix,
        log_level=settings.log_level,
        storage_provider=settings.storage_provider,
        cors_origins=settings.allowed_origins,
        swagger_enabled=settings.swagger_enabled,
        health_check_enabled=settings.health_check_enabled,
    )
