from typing import Any

from fastapi import APIRouter

from app.middleware.authentication import AuthenticatedContext
from app.schemas.company_dashboard import CompanyDashboardResponse
from app.schemas.registration import ErrorResponse
from app.services.company_dashboard_service import company_dashboard_service

router = APIRouter(prefix="/company", tags=["company-dashboard"])
ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Authentication is required."},
    403: {
        "model": ErrorResponse,
        "description": "Company Admin role and Dashboard View permission are required.",
    },
    404: {"model": ErrorResponse, "description": "Company dashboard context was not found."},
    500: {"model": ErrorResponse, "description": "Company dashboard could not be loaded."},
}


@router.get(
    "/dashboard",
    response_model=CompanyDashboardResponse,
    summary="Get current tenant dashboard",
    description=(
        "Returns Company Admin summary data derived only from the company identifier in the "
        "authenticated JWT. The endpoint does not accept a frontend company identifier."
    ),
    operation_id="get_company_dashboard",
    responses=ERRORS,
)
def get_company_dashboard(context: AuthenticatedContext) -> CompanyDashboardResponse:
    return company_dashboard_service.get_dashboard(context)
