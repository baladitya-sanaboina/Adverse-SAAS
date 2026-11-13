from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AssignmentOption(BaseModel):
    id: UUID
    name: str


class AssignmentOptionsResponse(BaseModel):
    roles: list[AssignmentOption]
    departments: list[AssignmentOption]
    branches: list[AssignmentOption]


class UserAssignmentUpdate(BaseModel):
    role_id: UUID
    department_id: UUID | None = None
    branch_id: UUID | None = None
    model_config = ConfigDict(extra="forbid")


class CompanyUserResponse(BaseModel):
    id: UUID
    name: str
    email: str
    status: str
    role_id: UUID
    role_name: str
    role_code: str
    department_id: UUID | None
    department_name: str | None
    branch_id: UUID | None
    branch_name: str | None


class CompanyUserListResponse(BaseModel):
    items: list[CompanyUserResponse]
    total: int
