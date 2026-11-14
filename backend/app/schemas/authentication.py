from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, SecretStr, model_validator

SignupRole = Literal["ADMIN", "MANAGER", "EMPLOYEE", "CLIENT"]


class LoginRequest(BaseModel):
    email: EmailStr
    password: SecretStr = Field(min_length=1, max_length=128)


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class SignupRequest(BaseModel):
    role: SignupRole
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: SecretStr = Field(min_length=12, max_length=128)
    confirm_password: SecretStr = Field(min_length=12, max_length=128)
    company_name: str | None = Field(default=None, min_length=2, max_length=150)
    company_code: str | None = Field(default=None, pattern=r"^[A-Z][A-Z0-9_-]{2,31}$")
    subscription_plan: str = Field(default="Starter", min_length=2, max_length=50)

    @model_validator(mode="after")
    def validate_signup(self) -> "SignupRequest":
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
        if self.role == "ADMIN":
            if not self.company_name or not self.company_name.strip():
                raise ValueError("Company name is required for admin signup.")
            if not self.company_code or not self.company_code.strip():
                raise ValueError("Company code is required for admin signup.")
        elif not self.company_code or not self.company_code.strip():
            raise ValueError("Company code is required for team signup.")
        return self


class SignupResponse(BaseModel):
    message: Literal[
        "Verification code sent. Complete OTP verification to activate your account."
    ] = "Verification code sent. Complete OTP verification to activate your account."
    email: EmailStr
    role: SignupRole
    company_code: str | None = None


class VerificationEmailRequest(BaseModel):
    email: EmailStr


class VerifyEmailOtpRequest(BaseModel):
    email: EmailStr
    otp: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class VerificationEmailResponse(BaseModel):
    message: Literal["Verification code sent."] = "Verification code sent."


class VerifyEmailResponse(BaseModel):
    message: Literal["Email verified successfully. You can now sign in."] = (
        "Email verified successfully. You can now sign in."
    )


class ForgotPasswordResponse(BaseModel):
    message: Literal["If the account is eligible, a password reset code has been sent."] = (
        "If the account is eligible, a password reset code has been sent."
    )


class ResetPasswordRequest(BaseModel):
    token: str | None = Field(default=None, min_length=32, max_length=512)
    email: EmailStr | None = None
    otp: str | None = Field(default=None, min_length=6, max_length=6, pattern=r"^\d{6}$")
    new_password: SecretStr = Field(min_length=12, max_length=128)
    confirm_password: SecretStr = Field(min_length=12, max_length=128)

    @model_validator(mode="after")
    def validate_password(self) -> "ResetPasswordRequest":
        if not self.token and not (self.email and self.otp):
            raise ValueError("Either reset token or email plus OTP is required.")
        password = self.new_password.get_secret_value()
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


class ResetPasswordResponse(BaseModel):
    message: Literal["Password reset successfully. Sign in with your new password."] = (
        "Password reset successfully. Sign in with your new password."
    )


class AuthenticatedCompany(BaseModel):
    id: UUID
    name: str
    code: str
    status: str


class AuthenticatedUser(BaseModel):
    id: UUID
    name: str
    email: EmailStr
    status: str
    role: str
    company: AuthenticatedCompany | None


class TokenPairResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: AuthenticatedUser


class RefreshTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class LogoutResponse(BaseModel):
    message: Literal["Session logged out successfully."] = "Session logged out successfully."


class AuthContext(BaseModel):
    user_id: UUID
    role: str
    company_id: UUID | None
    user_type: Literal["platform", "company"]
    session_id: UUID
    issued_at: datetime
    expires_at: datetime
