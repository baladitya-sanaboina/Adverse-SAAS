"""Web Push shapes (owner request 2026-11-15)."""

from pydantic import BaseModel, ConfigDict, Field


class PushKeyResponse(BaseModel):
    enabled: bool
    public_key: str


class PushKeys(BaseModel):
    p256dh: str = Field(min_length=10, max_length=200)
    auth: str = Field(min_length=4, max_length=100)


class PushSubscribeRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    endpoint: str = Field(min_length=10, max_length=1000, pattern=r"^https://")
    keys: PushKeys


class PushUnsubscribeRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    endpoint: str = Field(min_length=10, max_length=1000)
