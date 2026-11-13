from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.middleware.authentication import AuthenticatedContext
from app.schemas.registration import ErrorResponse
from app.schemas.subscription_enforcement import (
    CompanyUsageResponse,
    SubscriptionEnforcementResponse,
    SubscriptionValidationRequest,
)
from app.schemas.subscription_management import (
    CompanyPlanAssignmentRequest,
    CompanyPlanResponse,
    PlanCreateRequest,
    PlanListFilters,
    PlanListResponse,
    PlanResponse,
    PlanUpdateRequest,
)
from app.services.subscription_enforcement_service import subscription_enforcement_service
from app.services.subscription_management_service import subscription_management_service

router = APIRouter(tags=["subscription-management"])
ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Authentication is required."},
    403: {
        "model": ErrorResponse,
        "description": "The required SUBSCRIPTIONS action permission is missing.",
    },
    404: {"model": ErrorResponse, "description": "Plan or company does not exist."},
    409: {"model": ErrorResponse, "description": "Plan code conflict or inactive plan."},
    422: {"model": ErrorResponse, "description": "Request validation failed."},
}


@router.post(
    "/platform/subscription-plans",
    response_model=PlanResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create subscription plan",
    operation_id="create_subscription_plan",
    responses=ERRORS,
)
def create_plan(request: PlanCreateRequest, context: AuthenticatedContext) -> PlanResponse:
    return subscription_management_service.create(context, request)


@router.get(
    "/platform/subscription-plans",
    response_model=PlanListResponse,
    summary="List subscription plans",
    operation_id="list_subscription_plans",
    responses=ERRORS,
)
def list_plans(
    context: AuthenticatedContext,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str = Query("", max_length=100),
    plan_status: Literal["ACTIVE", "INACTIVE"] | None = Query(None, alias="status"),
    sort: Literal["newest", "oldest", "a-z", "z-a", "display-order"] = "display-order",
) -> PlanListResponse:
    return subscription_management_service.list(
        context,
        PlanListFilters(
            page=page, page_size=page_size, search=search, status=plan_status, sort=sort
        ),
    )


@router.get(
    "/platform/subscription-plans/{plan_id}",
    response_model=PlanResponse,
    summary="Get subscription plan",
    operation_id="get_subscription_plan",
    responses=ERRORS,
)
def get_plan(plan_id: UUID, context: AuthenticatedContext) -> PlanResponse:
    return subscription_management_service.get(context, plan_id)


@router.put(
    "/platform/subscription-plans/{plan_id}",
    response_model=PlanResponse,
    summary="Update subscription plan",
    operation_id="update_subscription_plan",
    responses=ERRORS,
)
def update_plan(
    plan_id: UUID, request: PlanUpdateRequest, context: AuthenticatedContext
) -> PlanResponse:
    return subscription_management_service.update(context, plan_id, request)


@router.patch(
    "/platform/companies/{company_id}/plan",
    response_model=CompanyPlanResponse,
    summary="Assign or change company subscription plan",
    operation_id="assign_company_subscription_plan",
    responses=ERRORS,
)
def assign_company_plan(
    company_id: UUID, request: CompanyPlanAssignmentRequest, context: AuthenticatedContext
) -> CompanyPlanResponse:
    return subscription_management_service.assign(context, company_id, request)


@router.get(
    "/platform/companies/{company_id}/usage",
    response_model=CompanyUsageResponse,
    summary="Get company subscription usage",
    operation_id="get_company_subscription_usage",
    responses=ERRORS,
)
def get_company_usage(company_id: UUID, context: AuthenticatedContext) -> CompanyUsageResponse:
    return subscription_enforcement_service.usage(context, company_id)


@router.post(
    "/platform/companies/{company_id}/subscription/validate",
    response_model=SubscriptionEnforcementResponse,
    summary="Validate company feature or usage limit",
    operation_id="validate_company_subscription",
    responses=ERRORS,
)
def validate_company_subscription(
    company_id: UUID,
    request: SubscriptionValidationRequest,
    context: AuthenticatedContext,
) -> SubscriptionEnforcementResponse:
    return subscription_enforcement_service.validate(context, company_id, request)
