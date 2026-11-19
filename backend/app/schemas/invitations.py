from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)

InvitationStatus = Literal["PENDING", "ACCEPTED", "EXPIRED", "REVOKED"]
InvitationRoleCode = Literal["COMPANY_EMPLOYEE", "COMPANY_MANAGER", "COMPANY_CLIENT"]


class InvitationCreate(BaseModel):
    # email: the internal login (name@adverseindia.com); notification_email: their own Gmail,
    # where the setup link, password resets and other outside mail go.
    email: EmailStr
    notification_email: EmailStr | None = None
    name: str | None = Field(default=None, min_length=2, max_length=100)
    phone_number: str = Field(pattern=r"^\+?[0-9 ()-]{7,24}$")
    role_code: InvitationRoleCode = "COMPANY_EMPLOYEE"
    client_id: UUID | None = None
    # Employees and managers (owner request 2026-11-19).
    designation: str | None = Field(default=None, max_length=120)
    department_id: UUID | None = None
    joining_date: date | None = None
    model_config = ConfigDict(extra="forbid")

    @field_validator("designation")
    @classmethod
    def normalize_designation(cls, value: str | None) -> str | None:
        return (value or "").strip() or None

    @field_validator("email", "notification_email")
    @classmethod
    def normalize_email(cls, value: EmailStr | None) -> str | None:
        return str(value).strip().lower() if value is not None else None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("phone_number")
    @classmethod
    def normalize_phone_number(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def validate_role_specific_fields(self) -> "InvitationCreate":
        if self.client_id is not None and self.role_code != "COMPANY_CLIENT":
            raise ValueError("Client link is supported only for client invitations.")
        if self.role_code == "COMPANY_CLIENT" and (
            self.designation or self.department_id or self.joining_date
        ):
            raise ValueError("Designation, department and joining date are for team members.")
        return self


class InvitationResponse(BaseModel):
    id: UUID
    email: EmailStr
    notification_email: EmailStr
    company_name: str
    invited_by_name: str
    role_code: InvitationRoleCode
    status: InvitationStatus
    expires_at: datetime
    accepted_at: datetime | None
    created_at: datetime


class InvitationListResponse(BaseModel):
    items: list[InvitationResponse]
    total: int


class InvitationValidationResponse(BaseModel):
    valid: bool
    email: EmailStr
    company_name: str
    role_code: InvitationRoleCode
    login_url: str
    expires_at: datetime


class InvitationAcceptRequest(BaseModel):
    token: str = Field(min_length=32, max_length=512)
    name: str = Field(min_length=2, max_length=100)
    password: SecretStr = Field(min_length=12, max_length=128)
    confirm_password: SecretStr = Field(min_length=12, max_length=128)
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_fields(self) -> "InvitationAcceptRequest":
        self.name = self.name.strip()
        if len(self.name) < 2:
            raise ValueError("Name must contain at least two characters.")
        password = self.password.get_secret_value()
        if password != self.confirm_password.get_secret_value():
            raise ValueError("Password and confirm password must match.")
        if not any(value.islower() for value in password):
            raise ValueError("Password must contain a lowercase letter.")
        if not any(value.isupper() for value in password):
            raise ValueError("Password must contain an uppercase letter.")
        if not any(value.isdigit() for value in password):
            raise ValueError("Password must contain a number.")
        if not any(not value.isalnum() for value in password):
            raise ValueError("Password must contain a special character.")
        return self


class InvitationAcceptedResponse(BaseModel):
    message: Literal["Account created successfully. You can now sign in."] = (
        "Account created successfully. You can now sign in."
    )
    email: EmailStr
    company_name: str
    role_code: InvitationRoleCode
    login_url: str


class InvitationActionResponse(BaseModel):
    message: str
