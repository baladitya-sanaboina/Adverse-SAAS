from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class CompanyDashboardCompany(BaseModel):
    id: UUID
    name: str
    logo_url: str | None


class CompanyDashboardUser(BaseModel):
    id: UUID
    name: str
    role: Literal["COMPANY_ADMIN"]


class CompanyDashboardStatistics(BaseModel):
    employees: int = Field(description="Total Company Employee users in the authenticated tenant.")
    projects: int = Field(
        description="Current tenant project usage recorded by subscription enforcement."
    )
    clients: int = Field(description="Total Company Client users in the authenticated tenant.")
    active_projects: int | None = Field(
        default=None, description="Reserved until the Project module is implemented."
    )
    completed_projects: int | None = Field(
        default=None, description="Reserved until the Project module is implemented."
    )
    finance_total: str | None = Field(
        default=None, description="Unavailable until a supported Finance data model is implemented."
    )


class CompanyDashboardActivity(BaseModel):
    action: str
    subject: str
    description: str
    occurred_at: datetime


class CompanyDashboardQuickAction(BaseModel):
    label: str
    href: str
    module: str
    action: str


class CompanyDashboardResponse(BaseModel):
    company: CompanyDashboardCompany
    current_user: CompanyDashboardUser
    statistics: CompanyDashboardStatistics
    recent_activity: list[CompanyDashboardActivity]
    quick_actions: list[CompanyDashboardQuickAction]
