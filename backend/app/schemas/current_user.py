from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr


class CurrentUserProfile(BaseModel):
    id: UUID
    name: str
    email: EmailStr
    status: str
    created_at: datetime
    profile_image_url: str | None = None


class CurrentUserCompany(BaseModel):
    id: UUID
    name: str
    code: str
    subscription_plan: str
    status: str
    subscription_features: dict[str, bool]


class CurrentUserRole(BaseModel):
    id: UUID
    name: str
    code: str


class CurrentUserPermission(BaseModel):
    module: str
    module_name: str
    action: str
    action_name: str


class CurrentUserResponse(BaseModel):
    user: CurrentUserProfile
    company: CurrentUserCompany | None
    role: CurrentUserRole
    permissions: list[CurrentUserPermission]
