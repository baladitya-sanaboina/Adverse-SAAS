from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

LeadSource = Literal["WEBSITE", "REFERRAL", "EMAIL", "PHONE", "SOCIAL", "OTHER"]
LeadStatus = Literal["NEW", "CONTACTED", "QUALIFIED", "LOST", "CONVERTED"]
OpportunityStage = Literal["NEW", "QUALIFIED", "PROPOSAL", "NEGOTIATION", "WON", "LOST"]
OpportunityStatus = Literal["OPEN", "CLOSED"]


class LeadCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    company_name: str = Field(default="", max_length=160)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, pattern=r"^\+?[0-9 ()-]{7,24}$")
    source: LeadSource = "OTHER"
    status: LeadStatus = "NEW"
    owner_id: UUID
    client_id: UUID | None = None
    notes: str = Field(default="", max_length=2000)
    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 2:
            raise ValueError("Lead name cannot be blank.")
        return normalized

    @field_validator("company_name", "notes")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr | None) -> str | None:
        return str(value).lower() if value is not None else None


class LeadUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    company_name: str | None = Field(default=None, max_length=160)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, pattern=r"^\+?[0-9 ()-]{7,24}$")
    source: LeadSource | None = None
    status: LeadStatus | None = None
    owner_id: UUID | None = None
    client_id: UUID | None = None
    notes: str | None = Field(default=None, max_length=2000)
    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if len(normalized) < 2:
            raise ValueError("Lead name cannot be blank.")
        return normalized

    @field_validator("company_name", "notes")
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
            raise ValueError("At least one lead field is required.")
        if "owner_id" in self.model_fields_set and self.owner_id is None:
            raise ValueError("Lead owner cannot be cleared.")
        return self


class LeadResponse(BaseModel):
    id: UUID
    company_id: UUID
    client_id: UUID | None
    owner_id: UUID
    owner_name: str
    name: str
    company_name: str
    email: EmailStr | None
    phone: str | None
    source: LeadSource
    status: LeadStatus
    notes: str
    created_at: datetime
    updated_at: datetime


class LeadListFilters(BaseModel):
    search: str = Field(default="", max_length=100)
    status: LeadStatus | None = None
    source: LeadSource | None = None
    owner_id: UUID | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class LeadListResponse(BaseModel):
    items: list[LeadResponse]
    page: int
    page_size: int
    total: int
    total_pages: int


class OpportunityCreate(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    description: str = Field(default="", max_length=3000)
    value: Decimal = Field(default=Decimal("0"), ge=0, max_digits=18, decimal_places=2)
    currency: str = Field(default="INR", pattern=r"^[A-Za-z]{3}$")
    stage: OpportunityStage = "NEW"
    owner_id: UUID
    client_id: UUID
    lead_id: UUID | None = None
    expected_close_date: date | None = None
    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 2:
            raise ValueError("Opportunity name cannot be blank.")
        return normalized

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str) -> str:
        return value.strip()

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()


class OpportunityUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=180)
    description: str | None = Field(default=None, max_length=3000)
    value: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    currency: str | None = Field(default=None, pattern=r"^[A-Za-z]{3}$")
    stage: OpportunityStage | None = None
    owner_id: UUID | None = None
    client_id: UUID | None = None
    lead_id: UUID | None = None
    expected_close_date: date | None = None
    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if len(normalized) < 2:
            raise ValueError("Opportunity name cannot be blank.")
        return normalized

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        return value.upper() if value is not None else None

    @model_validator(mode="after")
    def require_change(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one opportunity field is required.")
        if "owner_id" in self.model_fields_set and self.owner_id is None:
            raise ValueError("Opportunity owner cannot be cleared.")
        if "client_id" in self.model_fields_set and self.client_id is None:
            raise ValueError("Opportunity client cannot be cleared.")
        return self


class OpportunityResponse(BaseModel):
    id: UUID
    company_id: UUID
    client_id: UUID
    client_name: str
    lead_id: UUID | None
    owner_id: UUID
    owner_name: str
    name: str
    description: str
    value: Decimal
    currency: str
    stage: OpportunityStage
    status: OpportunityStatus
    expected_close_date: date | None
    created_at: datetime
    updated_at: datetime


class OpportunityListFilters(BaseModel):
    search: str = Field(default="", max_length=100)
    stage: OpportunityStage | None = None
    status: OpportunityStatus | None = None
    owner_id: UUID | None = None
    client_id: UUID | None = None
    lead_id: UUID | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class OpportunityListResponse(BaseModel):
    items: list[OpportunityResponse]
    page: int
    page_size: int
    total: int
    total_pages: int


class CrmOption(BaseModel):
    id: UUID
    name: str


class CrmOptionsResponse(BaseModel):
    owners: list[CrmOption]
    clients: list[CrmOption]
