from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.middleware.authentication import AuthenticatedContext
from app.middleware.permissions import require_permission
from app.schemas.company_onboarding import (
    CompanyOnboardingRequest,
    CompanyOnboardingResponse,
    CompanyOnboardingSummaryResponse,
)
from app.schemas.registration import ErrorResponse
from app.services.company_onboarding_service import company_onboarding_service

router = APIRouter(prefix="/platform/onboarding", tags=["company-onboarding"])
ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Authentication is required."},
    403: {"model": ErrorResponse, "description": "Company create/view permission is required."},
    404: {"model": ErrorResponse, "description": "Plan or onboarding was not found."},
    409: {
        "model": ErrorResponse,
        "description": "Company code, business email, or admin email already exists.",
    },
    422: {"model": ErrorResponse, "description": "Request validation failed."},
}


def _payload(record: Any) -> dict[str, Any]:
    payload = {
        "id": record.id,
        "status": record.status,
        "company": record.company,
        "subscription": record.subscription,
        "admin": record.admin,
        "initialization": record.initialization,
        "started_at": record.started_at,
        "completed_at": record.completed_at,
    }
    return payload


@router.post(
    "",
    response_model=CompanyOnboardingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Complete company onboarding",
    description="Atomically creates the tenant, assigns a plan, creates its Company Admin, copies platform defaults, and queues welcome delivery.",
    operation_id="complete_company_onboarding",
    responses=ERRORS,
)
def create_onboarding(
    request: CompanyOnboardingRequest,
    context: AuthenticatedContext,
    _permission: Annotated[None, Depends(require_permission("COMPANIES", "CREATE"))],
) -> CompanyOnboardingResponse:
    return CompanyOnboardingResponse(
        **_payload(company_onboarding_service.create(context, request))
    )


@router.get(
    "/{company_id}",
    response_model=CompanyOnboardingSummaryResponse,
    summary="Get company onboarding summary",
    description="Returns company, plan, admin, initialization, email, completion, and audit status.",
    operation_id="get_company_onboarding_summary",
    responses=ERRORS,
)
def get_onboarding(
    company_id: UUID,
    context: AuthenticatedContext,
    _permission: Annotated[None, Depends(require_permission("COMPANIES", "VIEW"))],
) -> CompanyOnboardingSummaryResponse:
    record = company_onboarding_service.get(context, company_id)
    return CompanyOnboardingSummaryResponse(**_payload(record), audit_trail=record.audit_trail)
