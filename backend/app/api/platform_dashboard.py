from typing import Any

from fastapi import APIRouter

from app.middleware.authentication import AuthenticatedContext
from app.schemas.platform_dashboard import PlatformDashboardResponse
from app.schemas.registration import ErrorResponse
from app.services.platform_dashboard_service import platform_dashboard_service

router = APIRouter(prefix="/platform", tags=["platform-dashboard"])
ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Bearer token or session is invalid."},
    403: {"model": ErrorResponse, "description": "Platform Owner role is required."},
    503: {"model": ErrorResponse, "description": "Dashboard dependencies are unavailable."},
}


@router.get(
    "/dashboard",
    response_model=PlatformDashboardResponse,
    summary="Get Platform Owner dashboard",
    description="Returns read-only platform statistics, recent activities, system health, and quick actions.",
    operation_id="get_platform_dashboard",
    responses=ERRORS,
)
def get_platform_dashboard(context: AuthenticatedContext) -> PlatformDashboardResponse:
    return platform_dashboard_service.get_dashboard(context)
