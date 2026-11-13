from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

UsageState = Literal["OK", "WARNING", "HIGH_USAGE", "LIMIT_REACHED", "UNLIMITED"]


class UsageMetricResponse(BaseModel):
    code: str
    label: str
    used: float
    limit: float | None
    remaining: float | None
    percentage: float | None
    state: UsageState
    unit: str
    upgrade_recommended: bool


class UsageAlertResponse(BaseModel):
    resource_code: str
    level: UsageState
    message: str


class CompanyUsageResponse(BaseModel):
    company_id: UUID
    company_name: str
    plan_id: UUID
    plan_name: str
    plan_code: str
    features: dict[str, bool]
    usage: list[UsageMetricResponse]
    alerts: list[UsageAlertResponse]
    upgrade_recommended: bool


class SubscriptionValidationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feature_code: str | None = Field(default=None, pattern=r"^[A-Z][A-Z0-9_]*$")
    resource_code: str | None = Field(default=None, pattern=r"^[A-Z][A-Z0-9_]*$")
    requested_increment: int = Field(default=1, ge=0)

    @model_validator(mode="after")
    def exactly_one_validation_target(self) -> "SubscriptionValidationRequest":
        if bool(self.feature_code) == bool(self.resource_code):
            raise ValueError("Provide exactly one feature_code or resource_code.")
        return self


class SubscriptionEnforcementResponse(BaseModel):
    company_id: UUID
    plan_code: str
    validation_type: Literal["FEATURE", "LIMIT"]
    code: str
    allowed: bool
    reason: str
    used: float | None = None
    limit: float | None = None
    remaining: float | None = None
    unlimited: bool = False
    state: UsageState | None = None
    upgrade_recommended: bool = False
