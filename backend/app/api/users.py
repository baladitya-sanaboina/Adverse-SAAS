from typing import Any

from fastapi import APIRouter

from app.middleware.authentication import AuthenticatedContext
from app.schemas.current_user import CurrentUserResponse
from app.schemas.registration import ErrorResponse
from app.services.current_user_service import current_user_service

router = APIRouter(prefix="/users", tags=["users"])
ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Bearer token or session is invalid."},
    403: {"model": ErrorResponse, "description": "User or company is not active."},
}


@router.get(
    "/me",
    response_model=CurrentUserResponse,
    summary="Get current authenticated user",
    description=(
        "Returns the authenticated user's safe profile, nullable company context, role, "
        "and role permissions after validating the JWT and active session."
    ),
    operation_id="get_current_user",
    responses=ERRORS,
)
def get_current_user(context: AuthenticatedContext) -> CurrentUserResponse:
    return current_user_service.get_current_user(context)
