from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

RoleStatus = Literal["ACTIVE", "INACTIVE"]


class RoleCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80, pattern=r"^[A-Za-z][A-Za-z0-9 &()/_-]*$")
    description: str = Field(default="", max_length=500)
    permissions: list[str] = Field(default_factory=list, max_length=250)
    model_config = ConfigDict(extra="forbid")

    @field_validator("name", "description")
    @classmethod
    def trim_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("permissions")
    @classmethod
    def unique_permissions(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(value))


class RoleUpdate(BaseModel):
    name: str | None = Field(
        default=None, min_length=2, max_length=80, pattern=r"^[A-Za-z][A-Za-z0-9 &()/_-]*$"
    )
    description: str | None = Field(default=None, max_length=500)
    status: RoleStatus | None = None
    permissions: list[str] | None = Field(default=None, max_length=250)
    model_config = ConfigDict(extra="forbid")

    @field_validator("name", "description")
    @classmethod
    def trim_optional_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("permissions")
    @classmethod
    def unique_optional_permissions(cls, value: list[str] | None) -> list[str] | None:
        return list(dict.fromkeys(value)) if value is not None else None

    @model_validator(mode="after")
    def has_changes(self) -> "RoleUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one role field is required.")
        return self


class PermissionActionOption(BaseModel):
    code: str
    name: str
    key: str


class PermissionModuleOption(BaseModel):
    code: str
    name: str
    actions: list[PermissionActionOption]


class PermissionCatalogResponse(BaseModel):
    modules: list[PermissionModuleOption]


class RoleSummaryResponse(BaseModel):
    id: UUID
    name: str
    code: str
    description: str
    status: RoleStatus
    is_system: bool
    user_count: int
    permission_count: int
    created_at: datetime
    updated_at: datetime


class RoleDetailResponse(RoleSummaryResponse):
    permissions: list[str]


class RoleListResponse(BaseModel):
    items: list[RoleSummaryResponse]
    total: int
