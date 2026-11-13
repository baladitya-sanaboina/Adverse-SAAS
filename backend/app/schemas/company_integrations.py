from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

IntegrationProvider = Literal["GOOGLE_DRIVE", "SLACK", "STRIPE"]
IntegrationStatus = Literal["NOT_CONFIGURED", "CONFIGURED", "CONNECTED", "DISCONNECTED", "ERROR"]


class IntegrationConfiguration(BaseModel):
    document_upload: bool = False
    document_download: bool = False
    project_notifications: bool = False
    task_notifications: bool = False
    important_alerts: bool = False
    billing_enabled: bool = False


class IntegrationUpdate(BaseModel):
    enabled: bool = False
    configuration: IntegrationConfiguration = Field(default_factory=IntegrationConfiguration)


class CompanyIntegrationResponse(BaseModel):
    provider: IntegrationProvider
    status: IntegrationStatus
    enabled: bool
    configuration: IntegrationConfiguration
    connected_at: datetime | None
    updated_at: datetime | None


class CompanyIntegrationListResponse(BaseModel):
    items: list[CompanyIntegrationResponse]


class WorkflowSettingsUpdate(BaseModel):
    task_notifications: bool = True
    project_updates: bool = True
    approval_flow: bool = False
    client_notifications: bool = True


class WorkflowSettingsResponse(WorkflowSettingsUpdate):
    updated_at: datetime | None = None
