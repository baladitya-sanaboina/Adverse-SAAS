from typing import Any
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.middleware.authentication import AuthenticatedContext
from app.schemas.invitations import (
    InvitationAcceptedResponse,
    InvitationAcceptRequest,
    InvitationActionResponse,
    InvitationCreate,
    InvitationListResponse,
    InvitationResponse,
    InvitationValidationResponse,
)
from app.schemas.registration import ErrorResponse
from app.services.invitation_service import invitation_service

router = APIRouter(prefix="/company/invitations", tags=["company-invitations"])
ERRORS: dict[int | str, dict[str, Any]] = {
    400: {"model": ErrorResponse, "description": "Invitation is invalid or unavailable."},
    401: {"model": ErrorResponse, "description": "Authentication is required."},
    403: {"model": ErrorResponse, "description": "Invitation permission is required."},
    404: {"model": ErrorResponse, "description": "Invitation was not found."},
    409: {"model": ErrorResponse, "description": "User or pending invitation already exists."},
    410: {"model": ErrorResponse, "description": "Invitation has expired."},
    422: {"model": ErrorResponse, "description": "Request validation failed."},
}


@router.post(
    "", response_model=InvitationResponse, status_code=status.HTTP_201_CREATED, responses=ERRORS
)
def create_invitation(
    request: InvitationCreate, context: AuthenticatedContext
) -> InvitationResponse:
    return invitation_service.create(context, request)


@router.get("", response_model=InvitationListResponse, responses=ERRORS)
def list_invitations(context: AuthenticatedContext) -> InvitationListResponse:
    return invitation_service.list(context)


@router.get("/validate", response_model=InvitationValidationResponse, responses=ERRORS)
def validate_invitation(
    token: str = Query(min_length=32, max_length=512)
) -> InvitationValidationResponse:
    return invitation_service.validate(token)


@router.post("/accept", response_model=InvitationAcceptedResponse, responses=ERRORS)
def accept_invitation(request: InvitationAcceptRequest) -> InvitationAcceptedResponse:
    return invitation_service.accept(request)


@router.get("/{invitation_id}", response_model=InvitationResponse, responses=ERRORS)
def get_invitation(invitation_id: UUID, context: AuthenticatedContext) -> InvitationResponse:
    return invitation_service.get(context, invitation_id)


@router.post("/{invitation_id}/resend", response_model=InvitationActionResponse, responses=ERRORS)
def resend_invitation(
    invitation_id: UUID, context: AuthenticatedContext
) -> InvitationActionResponse:
    return invitation_service.resend(context, invitation_id)


@router.post("/{invitation_id}/revoke", response_model=InvitationActionResponse, responses=ERRORS)
def revoke_invitation(
    invitation_id: UUID, context: AuthenticatedContext
) -> InvitationActionResponse:
    return invitation_service.revoke(context, invitation_id)
