from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, model_validator

DeveloperStatus = Literal["ACTIVE", "INACTIVE"]


class DeveloperPermission(BaseModel):
    module: str = Field(pattern=r"^[A-Z][A-Z0-9_]*$")
    action: str = Field(pattern=r"^[A-Z][A-Z0-9_]*$")


class DeveloperCreateRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=50)
    last_name: str = Field(min_length=1, max_length=50)
    email: EmailStr
    phone: str = Field(pattern=r"^\+?[0-9][0-9 ()-]{6,19}$")
    password: SecretStr = Field(min_length=12, max_length=128)
    confirm_password: SecretStr = Field(min_length=12, max_length=128)
    status: DeveloperStatus = "ACTIVE"
    permissions: list[DeveloperPermission] | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "first_name": "Asha",
                "last_name": "Dev",
                "email": "asha@example.com",
                "phone": "+91 98765 43210",
                "password": "StrongPass!123",
                "confirm_password": "StrongPass!123",
                "status": "ACTIVE",
                "permissions": [{"module": "COMPANIES", "action": "VIEW"}],
            }
        }
    )

    @model_validator(mode="after")
    def validate_password(self) -> "DeveloperCreateRequest":
        password = self.password.get_secret_value()
        if password != self.confirm_password.get_secret_value():
            raise ValueError("Password and confirm password must match.")
        if not all(
            (
                any(c.islower() for c in password),
                any(c.isupper() for c in password),
                any(c.isdigit() for c in password),
                any(not c.isalnum() for c in password),
            )
        ):
            raise ValueError("Password must include uppercase, lowercase, number, and symbol.")
        return self


class DeveloperUpdateRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=50)
    last_name: str = Field(min_length=1, max_length=50)
    phone: str = Field(pattern=r"^\+?[0-9][0-9 ()-]{6,19}$")
    status: DeveloperStatus
    permissions: list[DeveloperPermission]
    model_config = ConfigDict(extra="forbid")


class DeveloperStatusRequest(BaseModel):
    status: DeveloperStatus


class DeveloperAuditResponse(BaseModel):
    action: str
    actor_name: str
    details: str | None
    created_at: datetime


class DeveloperResponse(BaseModel):
    id: UUID
    first_name: str
    last_name: str
    name: str
    email: EmailStr
    phone: str
    status: str
    permissions: list[DeveloperPermission]
    created_at: datetime
    updated_at: datetime
    last_login: datetime | None
    audits: list[DeveloperAuditResponse] = []


class DeveloperListResponse(BaseModel):
    items: list[DeveloperResponse]
    page: int
    page_size: int
    total: int
    total_pages: int
    available_permissions: list[DeveloperPermission]


class DeveloperListFilters(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    search: str = Field(default="", max_length=100)
    status: DeveloperStatus | None = None
    created_from: date | None = None
    created_to: date | None = None
    sort: Literal["newest", "oldest", "a-z"] = "newest"
