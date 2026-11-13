from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator


class PlatformSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    platform_name: str = Field(min_length=2, max_length=80)
    primary_color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    secondary_color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    footer_text: str = Field(min_length=1, max_length=160)
    support_email: EmailStr
    support_phone: str | None = Field(default=None, max_length=30)
    default_timezone: str = Field(min_length=1, max_length=64)
    default_language: Literal["en"] = "en"
    default_company_status: Literal["ACTIVE", "INACTIVE", "SUSPENDED"] = "ACTIVE"
    default_user_status: Literal["ACTIVE", "PENDING_VERIFICATION"] = "PENDING_VERIFICATION"
    default_subscription_code: str = Field(pattern=r"^[A-Z0-9_]+$", max_length=40)


class SmtpSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    host: str = Field(min_length=1, max_length=255)
    port: int = Field(ge=1, le=65535)
    username: str = Field(default="", max_length=255)
    password: SecretStr | None = Field(default=None, max_length=1024)
    encryption: Literal["NONE", "STARTTLS", "SSL"] = "NONE"
    sender_name: str = Field(min_length=1, max_length=120)
    sender_email: EmailStr


class MaintenanceSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool
    message: str = Field(min_length=10, max_length=500)
    allowed_roles: list[Literal["PLATFORM_OWNER", "DEVELOPER"]] = Field(
        default=["PLATFORM_OWNER"], max_length=2
    )

    @field_validator("allowed_roles")
    @classmethod
    def require_platform_owner(cls, value: list[str]) -> list[str]:
        roles = list(dict.fromkeys(value))
        if "PLATFORM_OWNER" not in roles:
            raise ValueError("Platform Owner access cannot be disabled during maintenance.")
        return roles


class TestEmailRequest(BaseModel):
    email: EmailStr


class BrandingAssetResponse(BaseModel):
    asset: Literal["logo", "favicon"]
    url: str


class SmtpSettingsResponse(BaseModel):
    host: str
    port: int
    username: str
    encryption: str
    sender_name: str
    sender_email: str
    password_configured: bool
    connection_status: Literal["connected", "unavailable"]


class MaintenanceSettingsResponse(BaseModel):
    enabled: bool
    message: str
    allowed_roles: list[str]


class PublicMaintenanceResponse(BaseModel):
    enabled: bool
    message: str


class PlatformSettingsResponse(PlatformSettingsUpdate):
    id: str
    platform_logo_url: str | None
    favicon_url: str | None
    smtp: SmtpSettingsResponse
    maintenance: MaintenanceSettingsResponse
    created_at: datetime
    updated_at: datetime


class ActionResponse(BaseModel):
    code: str
    detail: str
