"""Content calendar (Phase 13): Admin routes under /company/calendar, client routes under
/client-portal/calendar. Access rules live in calendar_service."""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from fastapi import APIRouter, File, Query, Response, UploadFile
from fastapi.responses import FileResponse

from app.middleware.authentication import AuthenticatedContext
from app.schemas.calendar import (
    CalendarEntryCreate,
    CalendarEntryResponse,
    CalendarEntryUpdate,
    CalendarListResponse,
    CalendarTaskLink,
)
from app.schemas.registration import ErrorResponse
from app.services.calendar_service import calendar_service

router = APIRouter(prefix="/company/calendar", tags=["content-calendar"])
client_router = APIRouter(prefix="/client-portal/calendar", tags=["client-portal"])

ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Not signed in."},
    403: {"model": ErrorResponse, "description": "Not allowed for this role."},
    404: {"model": ErrorResponse, "description": "Entry, client or task not found."},
    409: {"model": ErrorResponse, "description": "The entry is already in production."},
    413: {"model": ErrorResponse, "description": "File too large."},
    422: {"model": ErrorResponse, "description": "Request validation failed."},
}


# -- admin -----------------------------------------------------------------------------------


@router.get(
    "", response_model=CalendarListResponse, summary="All clients' entries", responses=ERRORS
)
def admin_list(
    context: AuthenticatedContext,
    client_id: UUID | None = Query(None),
    start: date | None = Query(None),
    end: date | None = Query(None),
) -> CalendarListResponse:
    return calendar_service.admin_list(context, client_id, start, end)


@router.post(
    "",
    response_model=CalendarEntryResponse,
    status_code=201,
    summary="Add an entry for a client",
    responses=ERRORS,
)
def admin_create(
    request: CalendarEntryCreate, context: AuthenticatedContext
) -> CalendarEntryResponse:
    return calendar_service.admin_create(context, request)


@router.patch(
    "/{entry_id}", response_model=CalendarEntryResponse, summary="Change an entry", responses=ERRORS
)
def admin_update(
    entry_id: UUID, request: CalendarEntryUpdate, context: AuthenticatedContext
) -> CalendarEntryResponse:
    return calendar_service.admin_update(context, entry_id, request)


@router.delete("/{entry_id}", status_code=204, summary="Delete an entry", responses=ERRORS)
def admin_delete(entry_id: UUID, context: AuthenticatedContext) -> Response:
    calendar_service.admin_delete(context, entry_id)
    return Response(status_code=204)


@router.put(
    "/{entry_id}/task",
    response_model=CalendarEntryResponse,
    summary="Link a task to the entry (or unlink with null)",
    responses=ERRORS,
)
def admin_link_task(
    entry_id: UUID, request: CalendarTaskLink, context: AuthenticatedContext
) -> CalendarEntryResponse:
    return calendar_service.link_task(context, entry_id, request.task_id)


# -- client ----------------------------------------------------------------------------------


@client_router.get(
    "", response_model=CalendarListResponse, summary="My calendar entries", responses=ERRORS
)
def client_list(
    context: AuthenticatedContext,
    start: date | None = Query(None),
    end: date | None = Query(None),
) -> CalendarListResponse:
    return calendar_service.client_list(context, start, end)


@client_router.post(
    "",
    response_model=CalendarEntryResponse,
    status_code=201,
    summary="Add an entry to my calendar",
    responses=ERRORS,
)
def client_create(
    request: CalendarEntryCreate, context: AuthenticatedContext
) -> CalendarEntryResponse:
    return calendar_service.client_create(context, request)


@client_router.patch(
    "/{entry_id}",
    response_model=CalendarEntryResponse,
    summary="Change my entry or tick progress",
    responses=ERRORS,
)
def client_update(
    entry_id: UUID, request: CalendarEntryUpdate, context: AuthenticatedContext
) -> CalendarEntryResponse:
    return calendar_service.client_update(context, entry_id, request)


@client_router.delete("/{entry_id}", status_code=204, summary="Delete my entry", responses=ERRORS)
def client_delete(entry_id: UUID, context: AuthenticatedContext) -> Response:
    calendar_service.client_delete(context, entry_id)
    return Response(status_code=204)


# -- script file (same rules for both, checked in the service) -------------------------------


def _script_routes(target: APIRouter) -> None:
    @target.post(
        "/{entry_id}/script",
        response_model=CalendarEntryResponse,
        summary="Upload or replace the script file",
        responses=ERRORS,
    )
    def upload_script(
        entry_id: UUID, context: AuthenticatedContext, file: UploadFile = File(...)
    ) -> CalendarEntryResponse:
        return calendar_service.upload_script(context, entry_id, file)

    @target.get("/{entry_id}/script", summary="Download the script file", responses=ERRORS)
    def download_script(entry_id: UUID, context: AuthenticatedContext) -> FileResponse:
        path, name, mime = calendar_service.script_file(context, entry_id)
        return FileResponse(path, media_type=mime, filename=name)

    @target.delete(
        "/{entry_id}/script",
        response_model=CalendarEntryResponse,
        summary="Remove the script file",
        responses=ERRORS,
    )
    def delete_script(entry_id: UUID, context: AuthenticatedContext) -> CalendarEntryResponse:
        return calendar_service.delete_script(context, entry_id)


_script_routes(router)
_script_routes(client_router)
