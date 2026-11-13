from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class PlatformStatistics(BaseModel):
    total_companies: int
    total_developers: int
    total_employees: int
    total_clients: int
    total_active_users: int
    total_suspended_companies: int
    total_active_sessions: int


class PlatformActivity(BaseModel):
    action: str
    subject: str
    description: str
    occurred_at: datetime


class PlatformSystemHealth(BaseModel):
    backend: Literal["healthy", "unavailable"]
    database: Literal["healthy", "unavailable"]
    redis: Literal["healthy", "unavailable"]
    smtp: Literal["healthy", "unavailable"]
    storage: Literal["healthy", "unavailable"]
    api_version: str


class PlatformQuickAction(BaseModel):
    label: str
    href: str


class PlatformDashboardResponse(BaseModel):
    statistics: PlatformStatistics
    recent_activities: list[PlatformActivity]
    system_health: PlatformSystemHealth
    quick_actions: list[PlatformQuickAction]
