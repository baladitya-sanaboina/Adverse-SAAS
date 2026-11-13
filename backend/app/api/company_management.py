from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Query

from app.middleware.authentication import AuthenticatedContext
from app.schemas.company_management import (
    CompanyListFilters,
    CompanyListResponse,
    CompanyResponse,
    CompanyStatusRequest,
)
from app.schemas.registration import ErrorResponse
from app.services.company_management_service import company_management_service

router = APIRouter(prefix="/platform/companies", tags=["company-management"])
ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Authentication is required."},
    403: {"model": ErrorResponse, "description": "COMPANIES permission is required."},
    404: {"model": ErrorResponse, "description": "Company does not exist."},
    422: {"model": ErrorResponse, "description": "Request validation failed."},
}


@router.get(
    "", response_model=CompanyListResponse, summary="List managed companies", responses=ERRORS
)
def list_companies(
    context: AuthenticatedContext,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str = Query("", max_length=100),
    company_status: Literal["ACTIVE", "INACTIVE", "SUSPENDED", "PENDING"] | None = Query(
        None, alias="status"
    ),
    plan: Literal["Starter", "Professional", "Enterprise"] | None = None,
    sort: Literal["newest", "oldest", "a-z", "z-a"] = "newest",
) -> CompanyListResponse:
    return company_management_service.list(
        context,
        CompanyListFilters(
            page=page,
            page_size=page_size,
            search=search,
            status=company_status,
            plan=plan,
            sort=sort,
        ),
    )


@router.get(
    "/{company_id}", response_model=CompanyResponse, summary="Get managed company", responses=ERRORS
)
def get_company(company_id: UUID, context: AuthenticatedContext) -> CompanyResponse:
    return company_management_service.get(context, company_id)


@router.patch(
    "/{company_id}/status",
    response_model=CompanyResponse,
    summary="Update company status",
    responses=ERRORS,
)
def update_company_status(
    company_id: UUID, request: CompanyStatusRequest, context: AuthenticatedContext
) -> CompanyResponse:
    return company_management_service.update_status(context, company_id, request)
