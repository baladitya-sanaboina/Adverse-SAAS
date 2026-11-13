from typing import Any
from uuid import UUID

from fastapi import APIRouter

from app.middleware.authentication import AuthenticatedContext
from app.schemas.registration import ErrorResponse
from app.schemas.user_assignments import (
    AssignmentOptionsResponse,
    CompanyUserListResponse,
    CompanyUserResponse,
    UserAssignmentUpdate,
)
from app.services.user_assignment_service import user_assignment_service

router = APIRouter(prefix="/company/users", tags=["company-user-assignments"])
ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Authentication is required."},
    403: {
        "model": ErrorResponse,
        "description": "Company Admin assignment permission is required.",
    },
    404: {
        "model": ErrorResponse,
        "description": "Tenant-scoped user or assignment option was not found.",
    },
    422: {"model": ErrorResponse, "description": "Request validation failed."},
}


@router.get("", response_model=CompanyUserListResponse, responses=ERRORS)
def list_company_users(context: AuthenticatedContext) -> CompanyUserListResponse:
    return user_assignment_service.list_users(context)


@router.get("/assignment-options", response_model=AssignmentOptionsResponse, responses=ERRORS)
def assignment_options(context: AuthenticatedContext) -> AssignmentOptionsResponse:
    return user_assignment_service.options(context)


@router.patch("/{user_id}/organization", response_model=CompanyUserResponse, responses=ERRORS)
def update_user_assignment(
    user_id: UUID, request: UserAssignmentUpdate, context: AuthenticatedContext
) -> CompanyUserResponse:
    return user_assignment_service.assign(context, user_id, request)
