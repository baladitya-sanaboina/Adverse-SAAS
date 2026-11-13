from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

EmployeeStatus = Literal["PENDING", "ACTIVE", "INACTIVE"]


class EmployeeCreate(BaseModel):
    user_id: UUID
    employee_code: str = Field(min_length=2, max_length=30, pattern=r"^[A-Za-z0-9-]+$")
    department_id: UUID
    branch_id: UUID
    role_id: UUID
    status: EmployeeStatus = "PENDING"
    model_config = ConfigDict(extra="forbid")

    @field_validator("employee_code")
    @classmethod
    def normalize_employee_code(cls, value: str) -> str:
        return value.strip().upper()


class EmployeeUpdate(BaseModel):
    first_name: str | None = Field(default=None, max_length=60)
    last_name: str | None = Field(default=None, max_length=60)
    phone_number: str | None = Field(default=None, pattern=r"^\+?[0-9 ()-]{7,24}$")
    employee_code: str | None = Field(
        default=None, min_length=2, max_length=30, pattern=r"^[A-Za-z0-9-]+$"
    )
    department_id: UUID | None = None
    branch_id: UUID | None = None
    role_id: UUID | None = None
    status: EmployeeStatus | None = None
    model_config = ConfigDict(extra="forbid")

    @field_validator("employee_code")
    @classmethod
    def normalize_employee_code(cls, value: str | None) -> str | None:
        return value.strip().upper() if value is not None else None

    @model_validator(mode="after")
    def require_change(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one employee field is required.")
        return self


class EmployeeResponse(BaseModel):
    id: UUID
    company_id: UUID
    user_id: UUID
    user_name: str
    user_email: str
    first_name: str | None
    last_name: str | None
    phone_number: str | None
    user_status: str
    employee_code: str
    department_id: UUID | None
    department_name: str | None
    branch_id: UUID | None
    branch_name: str | None
    role_id: UUID
    role_name: str
    role_code: str
    status: EmployeeStatus
    created_at: datetime
    updated_at: datetime


class EmployeeListFilters(BaseModel):
    search: str = Field(default="", max_length=100)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    status: EmployeeStatus | None = None
    department_id: UUID | None = None
    branch_id: UUID | None = None
    role_id: UUID | None = None


class EmployeeListResponse(BaseModel):
    items: list[EmployeeResponse]
    page: int
    page_size: int
    total: int
    total_pages: int
