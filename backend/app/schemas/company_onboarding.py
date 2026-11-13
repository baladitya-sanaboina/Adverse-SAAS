from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl, SecretStr, model_validator


class OnboardingCompanyRequest(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_-]{2,31}$")
    business_email: EmailStr
    phone: str | None = Field(default=None, max_length=32)
    address: str | None = Field(default=None, max_length=500)
    website: HttpUrl | None = None
    timezone: str = Field(default="UTC", min_length=2, max_length=64)
    language: str = Field(default="en", pattern=r"^[a-z]{2}(?:-[A-Z]{2})?$")


class OnboardingAdminRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=60)
    last_name: str = Field(min_length=1, max_length=60)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=32)
    password: SecretStr = Field(min_length=12, max_length=128)
    confirm_password: SecretStr = Field(min_length=12, max_length=128)

    @model_validator(mode="after")
    def validate_password(self) -> "OnboardingAdminRequest":
        password = self.password.get_secret_value()
        if password != self.confirm_password.get_secret_value():
            raise ValueError("Password and confirm password must match.")
        checks = (
            any(char.islower() for char in password),
            any(char.isupper() for char in password),
            any(char.isdigit() for char in password),
            any(not char.isalnum() for char in password),
        )
        if not all(checks):
            raise ValueError("Password must include upper, lower, number, and special characters.")
        return self


class CompanyOnboardingRequest(BaseModel):
    company: OnboardingCompanyRequest
    subscription_plan_id: UUID
    admin: OnboardingAdminRequest

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "company": {
                    "name": "Acme Operations",
                    "code": "ACME_OPS",
                    "business_email": "hello@acme.example",
                    "phone": "+1 555 0100",
                    "address": "100 Market Street",
                    "website": "https://acme.example",
                    "timezone": "Asia/Kolkata",
                    "language": "en",
                },
                "subscription_plan_id": "00000000-0000-0000-0000-000000000001",
                "admin": {
                    "first_name": "Asha",
                    "last_name": "Rao",
                    "email": "asha@acme.example",
                    "phone": "+1 555 0101",
                    "password": "StrongPass!123",
                    "confirm_password": "StrongPass!123",
                },
            }
        }
    )


class OnboardingPlanResponse(BaseModel):
    id: UUID
    name: str
    code: str
    features: dict[str, bool]
    limits: dict[str, int | None]


class OnboardingCompanyResponse(BaseModel):
    id: UUID
    name: str
    code: str
    business_email: EmailStr
    phone: str | None
    address: str | None
    website: str | None
    timezone: str
    language: str
    status: str


class OnboardingAdminResponse(BaseModel):
    id: UUID
    name: str
    email: EmailStr
    phone: str | None
    role: Literal["COMPANY_ADMIN"]
    status: str


class OnboardingProgressResponse(BaseModel):
    company_created: bool
    subscription_assigned: bool
    admin_created: bool
    tenant_initialized: bool
    defaults_seeded: bool
    welcome_email: str


class CompanyOnboardingResponse(BaseModel):
    id: UUID
    status: str
    company: OnboardingCompanyResponse
    subscription: OnboardingPlanResponse
    admin: OnboardingAdminResponse
    initialization: OnboardingProgressResponse
    started_at: datetime
    completed_at: datetime | None


class OnboardingAuditResponse(BaseModel):
    action: str
    created_at: datetime
    details: dict[str, Any] | None = None


class CompanyOnboardingSummaryResponse(CompanyOnboardingResponse):
    audit_trail: list[OnboardingAuditResponse]
