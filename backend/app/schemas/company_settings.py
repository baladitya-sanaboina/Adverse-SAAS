from datetime import datetime
from typing import Literal
from zoneinfo import available_timezones

from pydantic import BaseModel, EmailStr, Field, HttpUrl, field_validator, model_validator

Day = Literal["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]


class GeneralSettings(BaseModel):
    company_name: str = Field(min_length=2, max_length=150)
    description: str | None = Field(default=None, max_length=1000)

    @field_validator("company_name")
    @classmethod
    def clean_company_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("description")
    @classmethod
    def clean_description(cls, value: str | None) -> str | None:
        cleaned = value.strip() if value else None
        return cleaned or None


class BrandingSettings(BaseModel):
    logo_url: str | None = None
    favicon_url: str | None = None
    primary_color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    secondary_color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    accent_color: str = Field(default="#0876ED", pattern=r"^#[0-9A-Fa-f]{6}$")
    info_color: str = Field(default="#2563A6", pattern=r"^#[0-9A-Fa-f]{6}$")
    success_color: str = Field(default="#16855B", pattern=r"^#[0-9A-Fa-f]{6}$")
    warning_color: str = Field(default="#B7791F", pattern=r"^#[0-9A-Fa-f]{6}$")
    danger_color: str = Field(default="#C2414F", pattern=r"^#[0-9A-Fa-f]{6}$")
    email_footer: str = Field(default="", max_length=500)

    @field_validator(
        "primary_color",
        "secondary_color",
        "accent_color",
        "info_color",
        "success_color",
        "warning_color",
        "danger_color",
    )
    @classmethod
    def normalize_brand_color(cls, value: str) -> str:
        """Store one canonical value so reset/reload comparisons stay stable."""
        return value.upper()


class ContactSettings(BaseModel):
    business_email: EmailStr | None = None
    support_email: EmailStr | None = None
    phone: str | None = Field(default=None, pattern=r"^\+?[0-9][0-9 ()-]{6,19}$")
    support_phone: str | None = Field(default=None, pattern=r"^\+?[0-9][0-9 ()-]{6,19}$")
    website: HttpUrl | None = None
    address: str | None = Field(default=None, max_length=500)
    gst_tax_id: str | None = Field(default=None, max_length=80)
    registration_number: str | None = Field(default=None, max_length=80)


class RegionalSettings(BaseModel):
    timezone: str = Field(min_length=1, max_length=80)
    language: str = Field(pattern=r"^[a-z]{2}(?:-[A-Z]{2})?$")
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    date_format: Literal["DD/MM/YYYY", "MM/DD/YYYY", "YYYY-MM-DD"]
    time_format: Literal["12_HOUR", "24_HOUR"]

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        if value not in available_timezones():
            raise ValueError("Use a valid IANA timezone.")
        return value


class NotificationSettings(BaseModel):
    email: bool = True
    system: bool = True
    maintenance: bool = True
    security: bool = True


class PreferenceSettings(BaseModel):
    working_days: list[Day] = Field(min_length=1)
    business_hours_start: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    business_hours_end: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    theme: Literal["light", "dark", "system"] = "system"

    @field_validator("working_days")
    @classmethod
    def unique_days(cls, value: list[Day]) -> list[Day]:
        if len(value) != len(set(value)):
            raise ValueError("Working days must be unique.")
        return value

    @model_validator(mode="after")
    def hours_in_order(self) -> "PreferenceSettings":
        if self.business_hours_start >= self.business_hours_end:
            raise ValueError("Business hours end must be later than start.")
        return self


class CompanySettingsUpdate(BaseModel):
    general: GeneralSettings
    branding: BrandingSettings
    contact: ContactSettings
    regional: RegionalSettings
    notifications: NotificationSettings
    preferences: PreferenceSettings


class CompanyPreferencesUpdate(BaseModel):
    notifications: NotificationSettings
    preferences: PreferenceSettings


class CompanySettingsResponse(CompanySettingsUpdate):
    company_id: str
    company_code: str
    updated_at: datetime


class BrandingAssetResponse(BaseModel):
    asset: Literal["logo", "favicon"]
    url: str | None


class CompanyBrandingResponse(BaseModel):
    company_id: str
    company_name: str
    logo_url: str | None
    favicon_url: str | None
    primary_color: str
    secondary_color: str
    accent_color: str
    info_color: str
    success_color: str
    warning_color: str
    danger_color: str
    updated_at: datetime
