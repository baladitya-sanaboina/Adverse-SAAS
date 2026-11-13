from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, model_validator

InvitationStatus = Literal["PENDING", "ACCEPTED", "EXPIRED", "REVOKED"]


class InvitationCreate(BaseModel):
    email: EmailStr
    model_config = ConfigDict(extra="forbid")


class InvitationResponse(BaseModel):
    id: UUID
    email: EmailStr
    company_name: str
    invited_by_name: str
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


class InvitationActionResponse(BaseModel):
    message: str
