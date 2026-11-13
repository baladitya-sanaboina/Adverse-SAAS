from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Query, Response, status

from app.middleware.authentication import AuthenticatedContext
from app.schemas.client import (
    ClientActivityListResponse,
    ClientContactCreate,
    ClientContactListResponse,
    ClientContactResponse,
    ClientContactUpdate,
    ClientCreate,
    ClientDetailResponse,
    ClientFeedbackCreate,
    ClientFeedbackListResponse,
    ClientFeedbackResponse,
    ClientFeedbackUpdate,
    ClientListFilters,
    ClientListResponse,
    ClientNoteCreate,
    ClientNoteListResponse,
    ClientNoteResponse,
    ClientNoteUpdate,
    ClientPortalDashboardResponse,
    ClientResponse,
    ClientUpdate,
)
from app.schemas.registration import ErrorResponse
from app.services.client_service import client_service

router = APIRouter(prefix="/clients", tags=["client-management"])
ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Authentication is required."},
    403: {
        "model": ErrorResponse,
        "description": "The corresponding tenant-scoped Clients permission is required.",
    },
    404: {
        "model": ErrorResponse,
        "description": "The tenant-scoped client or contact was not found.",
    },
    409: {
        "model": ErrorResponse,
        "description": "The client code or contact email conflicts inside its allowed scope.",
    },
    422: {"model": ErrorResponse, "description": "Request validation failed."},
}


@router.post(
    "",
    response_model=ClientResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a tenant-scoped client",
    description=(
        "Creates a client business record in the company derived from the authenticated JWT. "
        "A tenant identifier is never accepted from the request body."
    ),
    responses=ERRORS,
)
def create_client(request: ClientCreate, context: AuthenticatedContext) -> ClientResponse:
    return client_service.create(context, request)


@router.get(
    "",
    response_model=ClientListResponse,
    summary="List current tenant clients",
    description="Returns only clients owned by the authenticated user's company.",
    responses=ERRORS,
)
def list_clients(
    context: AuthenticatedContext,
    search: str = Query("", max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    client_status: Literal["ACTIVE", "INACTIVE"] | None = Query(None, alias="status"),
) -> ClientListResponse:
    return client_service.list(
        context,
        ClientListFilters(
            search=search.strip(), page=page, page_size=page_size, status=client_status
        ),
    )


@router.get(
    "/me/dashboard",
    response_model=ClientPortalDashboardResponse,
    summary="Get the authenticated client dashboard payload",
    description=(
        "Returns only the client profile linked to the authenticated Company Client account, plus "
        "client-specific pricing and dependency-aware work or billing placeholders."
    ),
    responses=ERRORS,
)
def get_client_portal_dashboard(context: AuthenticatedContext) -> ClientPortalDashboardResponse:
    return client_service.get_portal_dashboard(context)


@router.get(
    "/{client_id}",
    response_model=ClientDetailResponse,
    summary="Get a tenant-scoped client and its contacts",
    responses=ERRORS,
)
def get_client(client_id: UUID, context: AuthenticatedContext) -> ClientDetailResponse:
    return client_service.get(context, client_id)


@router.patch(
    "/{client_id}",
    response_model=ClientResponse,
    summary="Update a tenant-scoped client",
    responses=ERRORS,
)
def update_client(
    client_id: UUID, request: ClientUpdate, context: AuthenticatedContext
) -> ClientResponse:
    return client_service.update(context, client_id, request)


@router.post(
    "/{client_id}/contacts",
    response_model=ClientContactResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a client contact",
    description=(
        "Creates a contact only after confirming that the parent client belongs to the current "
        "tenant. Selecting a primary contact atomically clears the previous primary contact."
    ),
    responses=ERRORS,
)
def create_client_contact(
    client_id: UUID, request: ClientContactCreate, context: AuthenticatedContext
) -> ClientContactResponse:
    return client_service.create_contact(context, client_id, request)


@router.get(
    "/{client_id}/contacts",
    response_model=ClientContactListResponse,
    summary="List contacts for a tenant-scoped client",
    responses=ERRORS,
)
def list_client_contacts(
    client_id: UUID, context: AuthenticatedContext
) -> ClientContactListResponse:
    return client_service.list_contacts(context, client_id)


@router.patch(
    "/{client_id}/contacts/{contact_id}",
    response_model=ClientContactResponse,
    summary="Update a tenant-scoped client contact",
    responses=ERRORS,
)
def update_client_contact(
    client_id: UUID,
    contact_id: UUID,
    request: ClientContactUpdate,
    context: AuthenticatedContext,
) -> ClientContactResponse:
    return client_service.update_contact(context, client_id, contact_id, request)


@router.post(
    "/{client_id}/notes",
    response_model=ClientNoteResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["client-notes"],
    summary="Add an internal client note",
    description=(
        "Adds an internal note to a client in the authenticated company. The actor and tenant "
        "are derived from the JWT and client accounts cannot access this history."
    ),
    responses=ERRORS,
)
def create_client_note(
    client_id: UUID, request: ClientNoteCreate, context: AuthenticatedContext
) -> ClientNoteResponse:
    return client_service.create_note(context, client_id, request)


@router.get(
    "/{client_id}/notes",
    response_model=ClientNoteListResponse,
    tags=["client-notes"],
    summary="List internal client notes",
    description="Returns tenant-scoped internal notes newest first.",
    responses=ERRORS,
)
def list_client_notes(client_id: UUID, context: AuthenticatedContext) -> ClientNoteListResponse:
    return client_service.list_notes(context, client_id)


@router.patch(
    "/{client_id}/notes/{note_id}",
    response_model=ClientNoteResponse,
    tags=["client-notes"],
    summary="Update an internal client note",
    responses=ERRORS,
)
def update_client_note(
    client_id: UUID,
    note_id: UUID,
    request: ClientNoteUpdate,
    context: AuthenticatedContext,
) -> ClientNoteResponse:
    return client_service.update_note(context, client_id, note_id, request)


@router.delete(
    "/{client_id}/notes/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    tags=["client-notes"],
    summary="Delete an internal client note",
    responses=ERRORS,
)
def delete_client_note(client_id: UUID, note_id: UUID, context: AuthenticatedContext) -> Response:
    client_service.delete_note(context, client_id, note_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{client_id}/feedback",
    response_model=ClientFeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["client-feedback"],
    summary="Add client feedback",
    description="Adds tenant-scoped client feedback and records the authenticated actor.",
    responses=ERRORS,
)
def create_client_feedback(
    client_id: UUID, request: ClientFeedbackCreate, context: AuthenticatedContext
) -> ClientFeedbackResponse:
    return client_service.create_feedback(context, client_id, request)


@router.get(
    "/{client_id}/feedback",
    response_model=ClientFeedbackListResponse,
    tags=["client-feedback"],
    summary="List client feedback",
    description="Returns tenant-scoped client feedback newest first.",
    responses=ERRORS,
)
def list_client_feedback(
    client_id: UUID, context: AuthenticatedContext
) -> ClientFeedbackListResponse:
    return client_service.list_feedback(context, client_id)


@router.patch(
    "/{client_id}/feedback/{feedback_id}",
    response_model=ClientFeedbackResponse,
    tags=["client-feedback"],
    summary="Update client feedback",
    responses=ERRORS,
)
def update_client_feedback(
    client_id: UUID,
    feedback_id: UUID,
    request: ClientFeedbackUpdate,
    context: AuthenticatedContext,
) -> ClientFeedbackResponse:
    return client_service.update_feedback(context, client_id, feedback_id, request)


@router.get(
    "/{client_id}/activity",
    response_model=ClientActivityListResponse,
    tags=["client-activity"],
    summary="List client activity",
    description=(
        "Returns the newest-first tenant-scoped timeline for client, contact, note, and feedback "
        "changes implemented by this module."
    ),
    responses=ERRORS,
)
def list_client_activity(
    client_id: UUID, context: AuthenticatedContext
) -> ClientActivityListResponse:
    return client_service.list_activity(context, client_id)
