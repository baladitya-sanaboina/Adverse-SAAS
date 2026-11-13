from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

CompanyStatus = Literal["ACTIVE", "INACTIVE", "SUSPENDED", "PENDING"]


class CompanyStatusRequest(BaseModel):
    status: CompanyStatus


class CompanyAdminResponse(BaseModel):
    id: UUID | None
    name: str | None
    email: str | None
    status: str | None


class CompanyStatisticsResponse(BaseModel):
    total_users: int
    active_users: int
    inactive_users: int


class CompanyAuditResponse(BaseModel):
    action: str
    actor_name: str
    previous_status: str | None
    new_status: str | None
    created_at: datetime


class CompanySubscriptionSummary(BaseModel):
    plan_id: UUID | None = None
    plan_code: str | None = None
    status: str
    activation_date: datetime | None = None
    expiration_date: datetime | None = None
    features: dict[str, bool] = {}
    limits: dict[str, int | None] = {}


class CompanyResponse(BaseModel):
    id: UUID
    name: str
    code: str
    contact_email: str | None
    subscription_plan: str
    status: CompanyStatus
    company_admin: CompanyAdminResponse
    statistics: CompanyStatisticsResponse
    created_at: datetime
    updated_at: datetime
    recent_activity: list[CompanyAuditResponse] = []
    subscription: CompanySubscriptionSummary


class CompanySummaryResponse(BaseModel):
    total: int
    active: int
    inactive: int
    suspended: int
    pending: int


class CompanyListResponse(BaseModel):
    items: list[CompanyResponse]
    page: int
    page_size: int
    total: int
    total_pages: int
    summary: CompanySummaryResponse


class CompanyListFilters(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    search: str = Field(default="", max_length=100)
    status: CompanyStatus | None = None
    plan: Literal["Starter", "Professional", "Enterprise"] | None = None
    sort: Literal["newest", "oldest", "a-z", "z-a"] = "newest"
