from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator

from app.schemas.current_user import CurrentUserResponse


class ProfileSettings(BaseModel):
    timezone: str
    language: str
    theme_preference: str
    email_notifications: bool


class ProfileResponse(CurrentUserResponse):
    first_name: str | None
    last_name: str | None
    phone_number: str | None
    profile_image_url: str | None
    settings: ProfileSettings


class UpdateProfileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    first_name: str | None = Field(default=None, max_length=60)
    last_name: str | None = Field(default=None, max_length=60)
    phone_number: str | None = Field(default=None, pattern=r"^\+?[0-9 ()-]{7,24}$")
    timezone: str = Field(default="UTC", min_length=1, max_length=64)
    language: str = Field(default="en", pattern=r"^[a-z]{2}(-[A-Z]{2})?$")
    theme_preference: Literal["system", "light", "dark"] = "system"
    email_notifications: bool = True


class ChangePasswordRequest(BaseModel):
    current_password: SecretStr = Field(min_length=1, max_length=128)
    new_password: SecretStr = Field(min_length=12, max_length=128)
    confirm_password: SecretStr = Field(min_length=12, max_length=128)

    @model_validator(mode="after")
    def validate_password(self) -> "ChangePasswordRequest":
        password = self.new_password.get_secret_value()
        if password != self.confirm_password.get_secret_value():
            raise ValueError("New password and confirmation must match.")
        if not all(
            (
                any(c.islower() for c in password),
                any(c.isupper() for c in password),
                any(c.isdigit() for c in password),
                any(not c.isalnum() for c in password),
            )
        ):
            raise ValueError("New password must contain uppercase, lowercase, number, and symbol.")
        return self


class ProfileMessageResponse(BaseModel):
    message: str


class ProfileImageResponse(BaseModel):
    profile_image_url: str
    message: str = "Profile image updated successfully."
