from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

PlanStatus = Literal["ACTIVE", "INACTIVE"]
PlanSort = Literal["newest", "oldest", "a-z", "z-a", "display-order"]


class PlanPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=80)
    code: str = Field(min_length=2, max_length=40, pattern=r"^[A-Z0-9_]+$")
    description: str | None = Field(default=None, max_length=500)
    monthly_price: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=2)
    yearly_price: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=2)
    status: PlanStatus = "ACTIVE"
    display_order: int = Field(default=0, ge=0, le=10000)
    features: dict[str, bool] = Field(default_factory=dict)
    limits: dict[str, int | None] = Field(default_factory=dict)

    @field_validator("features")
    @classmethod
    def validate_features(cls, value: dict[str, bool]) -> dict[str, bool]:
        if len(value) > 50 or any(not key.isupper() for key in value):
            raise ValueError("Feature codes must be uppercase and limited to 50 entries.")
        return value

    @field_validator("limits")
    @classmethod
    def validate_limits(cls, value: dict[str, int | None]) -> dict[str, int | None]:
        if len(value) > 50 or any(not key.isupper() for key in value):
            raise ValueError("Limit codes must be uppercase and limited to 50 entries.")
        if any(item is not None and item < 0 for item in value.values()):
            raise ValueError("Limits must be non-negative or null for unlimited.")
        return value


class PlanCreateRequest(PlanPayload):
    pass


class PlanUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=80)
    description: str | None = Field(default=None, max_length=500)
    monthly_price: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=2)
    yearly_price: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=2)
    status: PlanStatus = "ACTIVE"
    display_order: int = Field(default=0, ge=0, le=10000)
    features: dict[str, bool] = Field(default_factory=dict)
    limits: dict[str, int | None] = Field(default_factory=dict)

    @field_validator("features")
    @classmethod
    def validate_features(cls, value: dict[str, bool]) -> dict[str, bool]:
        return PlanPayload.validate_features(value)

    @field_validator("limits")
    @classmethod
    def validate_limits(cls, value: dict[str, int | None]) -> dict[str, int | None]:
        return PlanPayload.validate_limits(value)


class PlanResponse(PlanPayload):
    id: UUID
    companies_using_plan: int
    created_at: datetime
    updated_at: datetime


class PlanListResponse(BaseModel):
    items: list[PlanResponse]
    page: int
    page_size: int
    total: int
    total_pages: int


class PlanListFilters(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    search: str = Field(default="", max_length=100)
    status: PlanStatus | None = None
    sort: PlanSort = "display-order"


class CompanyPlanAssignmentRequest(BaseModel):
    plan_id: UUID
    activation_date: datetime | None = None
    expiration_date: datetime | None = None

    @field_validator("expiration_date")
    @classmethod
    def expiration_must_be_future(cls, value: datetime | None) -> datetime | None:
        return value


class CompanyPlanResponse(BaseModel):
    company_id: UUID
    company_name: str
    plan: PlanResponse
    status: Literal["ACTIVE", "EXPIRED", "CANCELLED"]
    activation_date: datetime
    expiration_date: datetime | None
    change_type: Literal["ASSIGNED", "UPGRADE", "DOWNGRADE", "CHANGED"]


class SubscriptionValidationResponse(BaseModel):
    company_id: UUID
    plan_code: str
    feature_code: str | None = None
    limit_code: str | None = None
    allowed: bool
    limit: int | None = None
    unlimited: bool = False
