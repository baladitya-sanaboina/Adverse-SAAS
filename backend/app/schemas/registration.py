from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, model_validator


class ErrorResponse(BaseModel):
    code: str
    detail: str
    errors: list[dict[str, Any]] | None = None


class UserRegistrationFields(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: SecretStr = Field(min_length=12, max_length=128)
    confirm_password: SecretStr = Field(min_length=12, max_length=128)

    @model_validator(mode="after")
    def validate_password(self) -> "UserRegistrationFields":
        password = self.password.get_secret_value()
        if password != self.confirm_password.get_secret_value():
            raise ValueError("Password and confirm password must match.")
        if not any(character.islower() for character in password):
            raise ValueError("Password must contain a lowercase letter.")
        if not any(character.isupper() for character in password):
            raise ValueError("Password must contain an uppercase letter.")
        if not any(character.isdigit() for character in password):
            raise ValueError("Password must contain a number.")
        if not any(not character.isalnum() for character in password):
            raise ValueError("Password must contain a special character.")
        return self


class CreateDeveloperRequest(UserRegistrationFields):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Developer Name",
                "email": "developer@example.com",
                "password": "StrongPass!123",
                "confirm_password": "StrongPass!123",
            }
        }
    )


class CreateCompanyRequest(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_-]{2,31}$")
    subscription_plan: str = Field(min_length=2, max_length=50)
    contact_email: EmailStr | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Example Company",
                "code": "EXAMPLE_CO",
                "subscription_plan": "Starter",
                "contact_email": "contact@example.com",
            }
        }
    )


class CompanyUserRegistrationRequest(UserRegistrationFields):
    pass


class CreateCompanyAdminRequest(CompanyUserRegistrationRequest):
    company_id: UUID


class CreateCompanyOnboardingRequest(BaseModel):
    company: CreateCompanyRequest
    admin: CompanyUserRegistrationRequest


class CreateEmployeeRequest(CompanyUserRegistrationRequest):
    pass


class CreateClientRequest(CompanyUserRegistrationRequest):
    pass


class RegisteredUserResponse(BaseModel):
    id: UUID
    name: str
    email: EmailStr
    status: str
    role: str
    company_id: UUID | None
    created_at: datetime


class RegisteredCompanyResponse(BaseModel):
    id: UUID
    name: str
    code: str
    subscription_plan: str
    status: str
    contact_email: EmailStr | None
    created_at: datetime


class RegisteredCompanyOnboardingResponse(BaseModel):
    company: RegisteredCompanyResponse
    admin: RegisteredUserResponse
