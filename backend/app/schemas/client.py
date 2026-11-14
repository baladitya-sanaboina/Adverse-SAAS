from datetime import datetime
from decimal import Decimal
from typing import Literal, Self
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    HttpUrl,
    field_validator,
    model_validator,
)

from app.schemas.service_pricing import PricingModel, PricingOverviewResponse

ClientStatus = Literal["ACTIVE", "INACTIVE"]
ClientActivityType = Literal[
    "NOTE_ADDED",
    "NOTE_UPDATED",
    "NOTE_DELETED",
    "FEEDBACK_ADDED",
    "FEEDBACK_UPDATED",
    "CLIENT_UPDATED",
    "CONTACT_ADDED",
    "CONTACT_UPDATED",
]


class ClientCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    code: str = Field(min_length=2, max_length=30, pattern=r"^[A-Za-z0-9-]+$")
    email: EmailStr | None = None
    phone: str | None = Field(default=None, pattern=r"^\+?[0-9 ()-]{7,24}$")
    website: HttpUrl | None = None
    address: str = Field(default="", max_length=300)
    city: str = Field(default="", max_length=100)
    state: str = Field(default="", max_length=100)
    country: str = Field(default="", max_length=100)
    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 2:
            raise ValueError("Client name cannot be blank.")
        return normalized

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr | None) -> str | None:
        return str(value).lower() if value is not None else None

    @field_validator("address", "city", "state", "country")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return value.strip()


class ClientUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    code: str | None = Field(default=None, min_length=2, max_length=30, pattern=r"^[A-Za-z0-9-]+$")
    email: EmailStr | None = None
    phone: str | None = Field(default=None, pattern=r"^\+?[0-9 ()-]{7,24}$")
    website: HttpUrl | None = None
    address: str | None = Field(default=None, max_length=300)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, max_length=100)
    status: ClientStatus | None = None
    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if len(normalized) < 2:
            raise ValueError("Client name cannot be blank.")
        return normalized

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str | None) -> str | None:
        return value.strip().upper() if value is not None else None

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr | None) -> str | None:
        return str(value).lower() if value is not None else None

    @field_validator("address", "city", "state", "country")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @model_validator(mode="after")
    def require_change(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one client field is required.")
        return self


class ClientContactCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(default="", max_length=80)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, pattern=r"^\+?[0-9 ()-]{7,24}$")
    designation: str = Field(default="", max_length=120)
    is_primary: bool = False
    status: ClientStatus = "ACTIVE"
    model_config = ConfigDict(extra="forbid")

    @field_validator("first_name")
    @classmethod
    def normalize_first_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("First name cannot be blank.")
        return normalized

    @field_validator("last_name", "designation")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr | None) -> str | None:
        return str(value).lower() if value is not None else None


class ClientContactUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=80)
    last_name: str | None = Field(default=None, max_length=80)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, pattern=r"^\+?[0-9 ()-]{7,24}$")
    designation: str | None = Field(default=None, max_length=120)
    is_primary: bool | None = None
    status: ClientStatus | None = None
    model_config = ConfigDict(extra="forbid")

    @field_validator("first_name")
    @classmethod
    def normalize_first_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("First name cannot be blank.")
        return normalized

    @field_validator("last_name", "designation")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr | None) -> str | None:
        return str(value).lower() if value is not None else None

    @model_validator(mode="after")
    def require_change(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one contact field is required.")
        return self


class ClientContactResponse(BaseModel):
    id: UUID
    client_id: UUID
    first_name: str
    last_name: str
    email: EmailStr | None
    phone: str | None
    designation: str
    is_primary: bool
    status: ClientStatus
    created_at: datetime
    updated_at: datetime


class ClientResponse(BaseModel):
    id: UUID
    company_id: UUID
    account_user_id: UUID | None = None
    account_name: str | None = None
    account_email: EmailStr | None = None
    account_status: str | None = None
    name: str
    code: str
    email: EmailStr | None
    phone: str | None
    website: str | None
    address: str
    city: str
    state: str
    country: str
    status: ClientStatus
    created_at: datetime
    updated_at: datetime
    primary_contact_name: str | None = None
    primary_contact_email: EmailStr | None = None
    primary_contact_phone: str | None = None
    primary_contact_designation: str | None = None


class ClientDetailResponse(ClientResponse):
    contacts: list[ClientContactResponse]


class ClientListFilters(BaseModel):
    search: str = Field(default="", max_length=100)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    status: ClientStatus | None = None


class ClientListResponse(BaseModel):
    items: list[ClientResponse]
    page: int
    page_size: int
    total: int
    total_pages: int


class ClientContactListResponse(BaseModel):
    items: list[ClientContactResponse]
    total: int


class ClientTextCreate(BaseModel):
    content: str = Field(min_length=1, max_length=4000)
    model_config = ConfigDict(extra="forbid")

    @field_validator("content")
    @classmethod
    def normalize_content(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Content cannot be blank.")
        return normalized


class ClientTextUpdate(ClientTextCreate):
    pass


class ClientNoteCreate(ClientTextCreate):
    pass


class ClientNoteUpdate(ClientTextUpdate):
    pass


class ClientFeedbackCreate(ClientTextCreate):
    pass


class ClientFeedbackUpdate(ClientTextUpdate):
    pass


class ClientNoteResponse(BaseModel):
    id: UUID
    client_id: UUID
    created_by_id: UUID
    created_by_name: str
    content: str
    created_at: datetime
    updated_at: datetime


class ClientNoteListResponse(BaseModel):
    items: list[ClientNoteResponse]
    total: int


class ClientFeedbackResponse(BaseModel):
    id: UUID
    client_id: UUID
    created_by_id: UUID
    created_by_name: str
    content: str
    created_at: datetime
    updated_at: datetime


class ClientFeedbackListResponse(BaseModel):
    items: list[ClientFeedbackResponse]
    total: int


class ClientActivityResponse(BaseModel):
    id: UUID
    client_id: UUID
    actor_id: UUID
    actor_name: str
    type: ClientActivityType
    description: str
    created_at: datetime


class ClientActivityListResponse(BaseModel):
    items: list[ClientActivityResponse]
    total: int


ClientWorkFilter = Literal["ALL", "PENDING", "IN_PROGRESS", "SUBMITTED", "APPROVED", "COMPLETED"]


class ClientPortalWorkItemResponse(BaseModel):
    task_id: str
    title: str
    service: str | None = None
    assignment_summary: str | None = None
    status: str
    due_date: datetime | None = None
    completion_date: datetime | None = None
    approval_status: str | None = None
    final_output_url: str | None = None
    client_charge: Decimal | None = None


class ClientPortalWorkSummaryResponse(BaseModel):
    ready: bool
    message: str
    filters: list[ClientWorkFilter] = Field(default_factory=list)
    total_projects: int | None = None
    active_projects: int | None = None
    completed_videos: int | None = None
    pending_videos: int | None = None
    items: list[ClientPortalWorkItemResponse] = Field(default_factory=list)


class ClientPortalPaymentResponse(BaseModel):
    id: UUID
    amount: Decimal
    currency: str
    received_at: datetime
    reference: str | None = None
    notes: str | None = None


class ClientPortalPackageSummaryResponse(BaseModel):
    service_id: UUID
    service_name: str
    pricing_model: PricingModel
    amount: Decimal
    currency: str
    billing_period_label: str
    notes: str = ""


class ClientPortalBillingSummaryResponse(BaseModel):
    ready: bool
    message: str
    total_billed: Decimal | None = None
    amount_received: Decimal | None = None
    pending_amount: Decimal | None = None
    monthly_billing: Decimal | None = None
    payments: list[ClientPortalPaymentResponse] = Field(default_factory=list)


class ClientPortalDashboardResponse(BaseModel):
    client: ClientDetailResponse
    pricing: PricingOverviewResponse
    packages: list[ClientPortalPackageSummaryResponse] = Field(default_factory=list)
    work: ClientPortalWorkSummaryResponse
    billing: ClientPortalBillingSummaryResponse
