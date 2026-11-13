from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.middleware.authentication import AuthenticatedContext
from app.middleware.permissions import require_permission
from app.schemas.company_integrations import (
    CompanyIntegrationListResponse,
    CompanyIntegrationResponse,
    IntegrationProvider,
    IntegrationUpdate,
    WorkflowSettingsResponse,
    WorkflowSettingsUpdate,
)
from app.schemas.registration import ErrorResponse
from app.services.company_integrations_service import company_integrations_service

router = APIRouter(tags=["company-integrations-workflows"])
ERRORS: dict[int | str, dict[str, Any]] = {
    400: {"model": ErrorResponse, "description": "Integration configuration is invalid."},
    401: {"model": ErrorResponse, "description": "Authentication is required."},
    403: {"model": ErrorResponse, "description": "Company Settings permission is required."},
    404: {"model": ErrorResponse, "description": "Tenant integration was not found."},
    422: {"model": ErrorResponse, "description": "Provider or request validation failed."},
}


@router.get(
    "/company/integrations",
    response_model=CompanyIntegrationListResponse,
    operation_id="list_company_integrations",
    summary="List current tenant integration configuration",
    responses=ERRORS,
)
def list_integrations(
    context: AuthenticatedContext,
    _permission: Annotated[None, Depends(require_permission("SETTINGS", "VIEW"))],
) -> CompanyIntegrationListResponse:
    return company_integrations_service.list(context)


@router.get(
    "/company/integrations/{provider}",
    response_model=CompanyIntegrationResponse,
    operation_id="get_company_integration",
    summary="Get one current tenant integration configuration",
    responses=ERRORS,
)
def get_integration(
    provider: IntegrationProvider,
    context: AuthenticatedContext,
    _permission: Annotated[None, Depends(require_permission("SETTINGS", "VIEW"))],
) -> CompanyIntegrationResponse:
    return company_integrations_service.get(context, provider)


@router.put(
    "/company/integrations/{provider}",
    response_model=CompanyIntegrationResponse,
    operation_id="update_company_integration",
    summary="Configure a current tenant integration without storing credentials",
    responses=ERRORS,
)
def update_integration(
    provider: IntegrationProvider,
    request: IntegrationUpdate,
    context: AuthenticatedContext,
    _permission: Annotated[None, Depends(require_permission("SETTINGS", "MANAGE"))],
) -> CompanyIntegrationResponse:
    return company_integrations_service.update(context, provider, request)


@router.delete(
    "/company/integrations/{provider}",
    response_model=CompanyIntegrationResponse,
    operation_id="disconnect_company_integration",
    summary="Disconnect a configured current tenant integration",
    responses=ERRORS,
)
def disconnect_integration(
    provider: IntegrationProvider,
    context: AuthenticatedContext,
    _permission: Annotated[None, Depends(require_permission("SETTINGS", "MANAGE"))],
) -> CompanyIntegrationResponse:
    return company_integrations_service.disconnect(context, provider)


@router.get(
    "/company/workflow-settings",
    response_model=WorkflowSettingsResponse,
    operation_id="get_company_workflow_settings",
    summary="Get current tenant workflow switches",
    responses=ERRORS,
)
def get_workflow_settings(
    context: AuthenticatedContext,
    _permission: Annotated[None, Depends(require_permission("SETTINGS", "VIEW"))],
) -> WorkflowSettingsResponse:
    return company_integrations_service.workflow(context)


@router.put(
    "/company/workflow-settings",
    response_model=WorkflowSettingsResponse,
    operation_id="update_company_workflow_settings",
    summary="Update current tenant workflow switches",
    responses=ERRORS,
)
def update_workflow_settings(
    request: WorkflowSettingsUpdate,
    context: AuthenticatedContext,
    _permission: Annotated[None, Depends(require_permission("SETTINGS", "MANAGE"))],
) -> WorkflowSettingsResponse:
    return company_integrations_service.update_workflow(context, request)
