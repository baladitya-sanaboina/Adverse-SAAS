from datetime import date
from typing import Any, Literal

from fastapi import APIRouter, Query

from app.middleware.authentication import AuthenticatedContext
from app.schemas.audit_logs import AuditCategory, AuditLogFilters, AuditLogListResponse
from app.schemas.registration import ErrorResponse
from app.services.audit_log_service import audit_log_service

router = APIRouter(prefix="/platform/audit-logs", tags=["audit-logs"])
ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Authentication is required."},
    403: {"model": ErrorResponse, "description": "Platform Owner access is required."},
    422: {"model": ErrorResponse, "description": "Request validation failed."},
}


@router.get(
    "",
    response_model=AuditLogListResponse,
    summary="List platform audit logs",
    description=(
        "Returns a read-only, paginated view of critical Developer, Company, Subscription, "
        "Settings, Onboarding, Registration, and enforcement audit events."
    ),
    responses=ERRORS,
)
def list_audit_logs(
    context: AuthenticatedContext,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str = Query("", max_length=100),
    category: AuditCategory | None = None,
    audit_date: date | None = Query(None, alias="date"),
    sort: Literal["newest", "oldest"] = "newest",
) -> AuditLogListResponse:
    return audit_log_service.list(
        context,
        AuditLogFilters(
            page=page,
            page_size=page_size,
            search=search,
            category=category,
            date=audit_date,
            sort=sort,
        ),
    )
