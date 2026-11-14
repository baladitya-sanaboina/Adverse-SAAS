"""In-app notification shapes (Phase 10)."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class NotificationResponse(BaseModel):
    id: UUID
    type: str
    title: str
    body: str
    link: str
    data: dict[str, Any]
    read: bool
    created_at: datetime


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    unread_count: int


class UnreadCountResponse(BaseModel):
    unread_count: int


class MarkedReadResponse(BaseModel):
    marked: int
    unread_count: int
