from datetime import UTC, datetime
from datetime import date as Date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

AuditCategory = Literal[
    "DEVELOPER",
    "COMPANY",
    "SUBSCRIPTION",
    "PLATFORM_SETTINGS",
    "ONBOARDING",
    "COMPANY_SETTINGS",
    "REGISTRATION",
    "ENFORCEMENT",
    "ORGANIZATION",
    "INVITATION",
    "PROFILE",
    "AUTHENTICATION",
    "EMPLOYEE",
    "CRM",
]


class AuditLogFilters(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    search: str = Field(default="", max_length=100)
    category: AuditCategory | None = None
    date: Date | None = None
    sort: Literal["newest", "oldest"] = "newest"


class AuditLogResponse(BaseModel):
    id: UUID
    category: AuditCategory
    action: str
    actor_id: UUID | None
    actor_name: str
    actor_email: str
    company_id: UUID | None
    company_name: str | None
    target: str | None
    details: str | None
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def normalize_created_at_to_utc(cls, value: datetime) -> datetime:
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class AuditLogSummaryResponse(BaseModel):
    total: int
    categories: dict[str, int]


class AuditLogListResponse(BaseModel):
    items: list[AuditLogResponse]
    page: int
    page_size: int
    total: int
    total_pages: int
    summary: AuditLogSummaryResponse
