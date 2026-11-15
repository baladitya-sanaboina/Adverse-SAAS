"""Onboarding documents (owner request 2026-11-15)."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

PacketStatus = Literal["SENT", "OPENED", "COMPLETED", "CANCELLED", "EXPIRED"]


class TemplateResponse(BaseModel):
    kind: str
    audience: Literal["CLIENT", "EMPLOYEE"]
    label: str
    signable: bool
    subject: str
    body: str
    customised: bool
    placeholders: list[str]


class TemplateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: str = Field(min_length=2, max_length=200)
    body: str = Field(min_length=10, max_length=30000)


class PacketResponse(BaseModel):
    id: UUID
    audience: Literal["CLIENT", "EMPLOYEE"]
    client_id: UUID | None
    user_id: UUID | None
    recipient_name: str
    recipient_email: str
    documents: list[str]
    fields: dict[str, Any]
    status: PacketStatus
    expires_at: datetime
    opened_at: datetime | None
    signed_name: str | None
    signed_at: datetime | None
    signed_ip: str | None
    form_data: dict[str, Any]
    sent_count: int
    created_by_name: str | None
    created_at: datetime


class ClientOnboardingRow(BaseModel):
    client_id: UUID
    name: str
    email: str | None
    created_at: datetime
    window_ends_at: datetime
    can_send: bool
    packet: PacketResponse | None


class StaffChoice(BaseModel):
    id: UUID
    name: str
    email: str
    role: Literal["MANAGER", "EMPLOYEE"]


class OnboardingOverview(BaseModel):
    window_hours: int
    clients: list[ClientOnboardingRow]
    employees: list[PacketResponse]
    staff: list[StaffChoice]
    templates: list[TemplateResponse]


class EmployeeDocumentsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: UUID | None = None
    name: str = Field(default="", max_length=160)
    email: EmailStr | None = None
    documents: list[
        Literal["EMPLOYEE_WELCOME", "EMPLOYEE_OFFER", "EMPLOYEE_JOINING", "EMPLOYEE_AGREEMENT"]
    ] = Field(min_length=1)
    job_title: str = Field(min_length=2, max_length=120)
    monthly_salary: Decimal = Field(ge=0, le=Decimal("99999999.99"), decimal_places=2)
    joining_date: date
    reporting_to: str = Field(default="", max_length=120)
    work_location: str = Field(default="", max_length=160)
    probation_months: int = Field(default=3, ge=0, le=24)
    notice_days: int = Field(default=30, ge=0, le=180)


class PublicDocument(BaseModel):
    kind: str
    label: str
    signable: bool
    title: str
    body: str


class PublicField(BaseModel):
    key: str
    label: str
    required: bool
    multiline: bool = False
    placeholder: str = ""


class PublicPacket(BaseModel):
    company_name: str
    audience: Literal["CLIENT", "EMPLOYEE"]
    recipient_name: str
    status: PacketStatus
    expires_at: datetime
    intro: str
    documents: list[PublicDocument]
    form: list[PublicField]
    form_data: dict[str, Any]
    signed_name: str | None
    signed_at: datetime | None


class PublicSubmit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    form: dict[str, str] = Field(default_factory=dict)
    signed_name: str = Field(min_length=2, max_length=160)
    accept: bool
