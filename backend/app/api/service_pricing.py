from typing import Any
from uuid import UUID

from fastapi import APIRouter, Query, Response, status

from app.middleware.authentication import AuthenticatedContext
from app.schemas.registration import ErrorResponse
from app.schemas.service_pricing import (
    CompanyServiceCreate,
    CompanyServiceDetailResponse,
    CompanyServiceListFilters,
    CompanyServiceListResponse,
    CompanyServiceResponse,
    CompanyServiceUpdate,
    PricingChangeRequest,
    PricingOverviewResponse,
    ServicePricingRecordResponse,
    ServiceStatus,
)
from app.services.service_pricing_service import service_pricing_service

router = APIRouter(prefix="/company/services", tags=["service-pricing"])
ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Authentication is required."},
    403: {
        "model": ErrorResponse,
        "description": "Company Admin settings permissions are required.",
    },
    404: {
        "model": ErrorResponse,
        "description": "The requested tenant-scoped service, client, or manager was not found.",
    },
    409: {
        "model": ErrorResponse,
        "description": "The request conflicts with existing service or pricing history.",
    },
    422: {"model": ErrorResponse, "description": "Request validation failed."},
}


@router.get(
    "",
    response_model=CompanyServiceListResponse,
    summary="List tenant-scoped services",
    responses=ERRORS,
)
def list_services(
    context: AuthenticatedContext,
    search: str = Query("", max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service_status: ServiceStatus | None = Query(None, alias="status"),
) -> CompanyServiceListResponse:
    return service_pricing_service.list_services(
        context,
        CompanyServiceListFilters(
            search=search.strip(), page=page, page_size=page_size, status=service_status
        ),
    )


@router.post(
    "",
    response_model=CompanyServiceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a tenant-scoped service",
    responses=ERRORS,
)
def create_service(
    request: CompanyServiceCreate, context: AuthenticatedContext
) -> CompanyServiceResponse:
    return service_pricing_service.create_service(context, request)


@router.get(
    "/pricing/clients/{client_id}",
    response_model=PricingOverviewResponse,
    summary="List client-specific pricing across services",
    responses=ERRORS,
)
def get_client_pricing(
    client_id: UUID,
    context: AuthenticatedContext,
    include_history: bool = Query(False),
) -> PricingOverviewResponse:
    return service_pricing_service.get_client_pricing(context, client_id, include_history)


@router.put(
    "/pricing/clients/{client_id}/services/{service_id}",
    response_model=ServicePricingRecordResponse,
    summary="Set or revise client service pricing",
    responses=ERRORS,
)
def set_client_pricing(
    client_id: UUID,
    service_id: UUID,
    request: PricingChangeRequest,
    context: AuthenticatedContext,
) -> ServicePricingRecordResponse:
    return service_pricing_service.set_client_pricing(context, client_id, service_id, request)


@router.get(
    "/pricing/managers/{manager_user_id}",
    response_model=PricingOverviewResponse,
    summary="List manager-specific pricing across services",
    responses=ERRORS,
)
def get_manager_pricing(
    manager_user_id: UUID,
    context: AuthenticatedContext,
    include_history: bool = Query(False),
) -> PricingOverviewResponse:
    return service_pricing_service.get_manager_pricing(context, manager_user_id, include_history)


@router.put(
    "/pricing/managers/{manager_user_id}/services/{service_id}",
    response_model=ServicePricingRecordResponse,
    summary="Set or revise manager service pricing",
    responses=ERRORS,
)
def set_manager_pricing(
    manager_user_id: UUID,
    service_id: UUID,
    request: PricingChangeRequest,
    context: AuthenticatedContext,
) -> ServicePricingRecordResponse:
    return service_pricing_service.set_manager_pricing(
        context, manager_user_id, service_id, request
    )


@router.get(
    "/{service_id}",
    response_model=CompanyServiceDetailResponse,
    summary="Get a service and pricing summary",
    responses=ERRORS,
)
def get_service(service_id: UUID, context: AuthenticatedContext) -> CompanyServiceDetailResponse:
    return service_pricing_service.get_service(context, service_id)


@router.patch(
    "/{service_id}",
    response_model=CompanyServiceResponse,
    summary="Update a tenant-scoped service",
    responses=ERRORS,
)
def update_service(
    service_id: UUID,
    request: CompanyServiceUpdate,
    context: AuthenticatedContext,
) -> CompanyServiceResponse:
    return service_pricing_service.update_service(context, service_id, request)


@router.delete(
    "/{service_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a tenant-scoped service when no pricing history exists",
    responses=ERRORS,
)
def delete_service(service_id: UUID, context: AuthenticatedContext) -> Response:
    service_pricing_service.delete_service(context, service_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
