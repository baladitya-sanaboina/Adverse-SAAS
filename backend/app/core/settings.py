from functools import lru_cache
from typing import Literal, Self

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = "Adverse API"
    app_version: str = "0.37.0"
    app_description: str = "Adverse platform and company service API"
    app_author: str = "Adverse"
    environment: Literal["development", "test", "staging", "production"] = "development"
    api_prefix: str = ""

    database_url: str
    redis_url: str

    jwt_secret: SecretStr = Field(min_length=32)
    jwt_expiry_minutes: int = Field(default=30, gt=0, le=10080)
    jwt_refresh_expiry_days: int = Field(default=7, gt=0, le=365)
    password_reset_expiry_minutes: int = Field(default=30, gt=0, le=1440)
    email_verification_expiry_minutes: int = Field(default=60, gt=0, le=1440)
    email_verification_resend_seconds: int = Field(default=60, gt=0, le=3600)
    invitation_expiry_hours: int = Field(default=48, gt=0, le=168)
    login_max_failed_attempts: int = Field(default=5, ge=3, le=20)
    account_lock_minutes: int = Field(default=15, gt=0, le=1440)

    storage_provider: Literal["local", "s3", "gcs", "azure"] = "local"
    smtp_host: str = ""
    smtp_port: int = Field(default=587, gt=0, le=65535)
    smtp_username: str = ""
    smtp_password: SecretStr = SecretStr("")
    smtp_from_email: str = ""
    smtp_from_name: str = "Adverse"
    smtp_use_tls: bool = True
    # The same mail about the same thing is not sent again within this window (owner request
    # 2026-11-15: a task submitted, sent back and submitted again mails once).
    mail_repeat_window_minutes: int = Field(default=30, ge=0, le=1440)
    # Meet relay (coturn with use-auth-secret). Empty TURN_URLS = STUN only, fine on most home
    # networks; strict office or mobile networks need the relay. Example:
    # TURN_URLS=turn:turn.example.com:3478?transport=udp,turns:turn.example.com:5349
    turn_urls: str = ""
    turn_secret: SecretStr = SecretStr("")
    turn_ttl_seconds: int = Field(default=6 * 3600, ge=300, le=86400)
    # Web Push (VAPID): notifications reach phones and desktops even when the app is closed.
    # Empty keys = no push (the bell and in-page alerts still work).
    vapid_public_key: str = ""
    vapid_private_key: SecretStr = SecretStr("")
    vapid_subject: str = "mailto:admin@localhost"

    cors_origins: str = (
        "http://localhost:3000,http://localhost:3001,http://localhost:3002,http://localhost:3003"
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    swagger_enabled: bool = True
    health_check_enabled: bool = True
    public_signup_enabled: bool = False

    swagger_contact_name: str = "Adverse API Team"
    swagger_contact_email: str = "api@adverse.example.com"
    swagger_contact_url: str = "https://adverse.local"

    @field_validator("app_name", "app_version", "database_url", "redis_url")
    @classmethod
    def required_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be empty")
        return value.strip()

    @field_validator("api_prefix")
    @classmethod
    def valid_api_prefix(cls, value: str) -> str:
        value = value.strip().rstrip("/")
        if value and not value.startswith("/"):
            raise ValueError("must be empty or begin with '/'")
        return value

    @model_validator(mode="after")
    def validate_production_safety(self) -> Self:
        if self.environment == "production":
            secret = self.jwt_secret.get_secret_value().lower()
            if "development" in secret or "change-me" in secret:
                raise ValueError("JWT_SECRET must be replaced for production")
            if not self.smtp_host or not self.smtp_from_email:
                raise ValueError("SMTP_HOST and SMTP_FROM_EMAIL are required in production")
            # The interactive API docs list every route; never publish them in production.
            self.swagger_enabled = False
        return self

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    def role_origin(self, role: str, purpose: str) -> str:
        role_index = {
            "PLATFORM_OWNER": 0,
            "DEVELOPER": 0,
            "COMPANY_ADMIN": 0,
            "COMPANY_MANAGER": 1,
            "COMPANY_EMPLOYEE": 2,
            "COMPANY_CLIENT": 3,
        }.get(role, 0)
        origins = self.allowed_origins
        if not origins:
            raise ValueError(f"At least one CORS origin is required for {purpose}")
        return origins[role_index] if len(origins) > role_index else origins[0]

    def password_reset_url(self, role: str, token: str) -> str:
        return f"{self.role_origin(role, 'password recovery')}/reset-password?token={token}"

    def email_verification_url(self, role: str, token: str) -> str:
        return f"{self.role_origin(role, 'email verification')}/verify-email?token={token}"

    def login_url(self, role: str) -> str:
        return f"{self.role_origin(role, 'login')}/login"

    def invitation_url(self, token: str) -> str:
        origins = self.allowed_origins
        if not origins:
            raise ValueError("At least one CORS origin is required for invitations")
        origin = origins[0]
        return f"{origin}/invitations/accept?token={token}"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
