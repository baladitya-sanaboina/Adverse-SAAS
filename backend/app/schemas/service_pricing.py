from datetime import datetime
from decimal import Decimal
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ServiceStatus = Literal["ACTIVE", "INACTIVE"]
PricingModel = Literal[
    "PER_VIDEO",
    "PER_PIECE",
    "MONTHLY_FIXED",
    "MONTHLY_PACKAGE",
    "COMMISSION_PER_DELIVERABLE",
]
PricingScope = Literal["CLIENT", "MANAGER"]


class CompanyServiceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=500)
    client_pricing_model: PricingModel = "PER_VIDEO"
    manager_pricing_model: PricingModel = "COMMISSION_PER_DELIVERABLE"
    status: ServiceStatus = "ACTIVE"
    sort_order: int = Field(default=0, ge=0, le=10000)
    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 2:
            raise ValueError("Service name cannot be blank.")
        return normalized

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str) -> str:
        return value.strip()


class CompanyServiceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    client_pricing_model: PricingModel | None = None
    manager_pricing_model: PricingModel | None = None
    status: ServiceStatus | None = None
    sort_order: int | None = Field(default=None, ge=0, le=10000)
    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if len(normalized) < 2:
            raise ValueError("Service name cannot be blank.")
        return normalized

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @model_validator(mode="after")
    def require_change(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one service field is required.")
        return self


class CompanyServiceResponse(BaseModel):
    id: UUID
    company_id: UUID
    name: str
    code: str
    description: str
    client_pricing_model: PricingModel
    manager_pricing_model: PricingModel
    status: ServiceStatus
    sort_order: int
    created_at: datetime
    updated_at: datetime
    active_client_rates: int
    active_manager_rates: int
    pricing_history_entries: int
    safe_to_delete: bool


class CompanyServiceDetailResponse(CompanyServiceResponse):
    pass


class CompanyServiceListFilters(BaseModel):
    search: str = Field(default="", max_length=100)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    status: ServiceStatus | None = None


class CompanyServiceListResponse(BaseModel):
    items: list[CompanyServiceResponse]
    page: int
    page_size: int
    total: int
    total_pages: int


class PricingChangeRequest(BaseModel):
    pricing_model: PricingModel | None = None
    amount: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    effective_from: datetime | None = None
    notes: str | None = Field(default=None, max_length=500)
    model_config = ConfigDict(extra="forbid")

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class PricingSubjectSummary(BaseModel):
    id: UUID
    name: str
    subtitle: str


class ServicePricingRecordResponse(BaseModel):
    id: UUID
    scope: PricingScope
    pricing_model: PricingModel
    amount: Decimal
    currency: str
    notes: str
    effective_from: datetime
    effective_to: datetime | None
    created_by_id: UUID
    created_by_name: str
    created_at: datetime


class SubjectServicePricingItemResponse(BaseModel):
    service_id: UUID
    service_name: str
    service_code: str
    service_description: str
    service_status: ServiceStatus
    default_pricing_model: PricingModel
    configured: bool
    current_rate: ServicePricingRecordResponse | None = None
    history_count: int = 0
    history: list[ServicePricingRecordResponse] = Field(default_factory=list)


class PricingOverviewResponse(BaseModel):
    scope: PricingScope
    subject: PricingSubjectSummary
    items: list[SubjectServicePricingItemResponse]
    total_services: int
    configured_services: int
    missing_services: int
