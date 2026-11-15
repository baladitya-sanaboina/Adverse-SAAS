"""Calendar with events and todos (owner request 2026-11-15). agenda_service decides who sees what."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Response

from app.middleware.authentication import AuthenticatedContext
from app.schemas.agenda import (
    AgendaEvent,
    AgendaFeed,
    AgendaPerson,
    AgendaTodo,
    EventRequest,
    EventUpdate,
    RespondRequest,
    Scope,
    TodoRequest,
    TodoUpdate,
)
from app.schemas.registration import ErrorResponse
from app.services.agenda_service import agenda_service

router = APIRouter(prefix="/agenda", tags=["calendar"])
ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Authentication is required."},
    403: {"model": ErrorResponse, "description": "Not allowed."},
    404: {"model": ErrorResponse, "description": "Not found."},
    422: {"model": ErrorResponse, "description": "Request validation failed."},
}


@router.get(
    "", response_model=AgendaFeed, summary="Events, meetings, deadlines and todos", responses=ERRORS
)
def feed(
    context: AuthenticatedContext,
    start: datetime,
    end: datetime,
    scope: Scope = "team",
    person: UUID | None = None,
) -> AgendaFeed:
    return agenda_service.feed(context, start, end, scope, person)


@router.get(
    "/people", response_model=list[AgendaPerson], summary="People I can invite", responses=ERRORS
)
def people(context: AuthenticatedContext) -> list[AgendaPerson]:
    return agenda_service.people(context)


@router.get("/todos", response_model=list[AgendaTodo], summary="My todos", responses=ERRORS)
def todos(context: AuthenticatedContext) -> list[AgendaTodo]:
    return agenda_service.todos(context)


@router.post(
    "/todos", response_model=AgendaTodo, status_code=201, summary="Add a todo", responses=ERRORS
)
def create_todo(request: TodoRequest, context: AuthenticatedContext) -> AgendaTodo:
    return agenda_service.create_todo(context, request)


@router.patch(
    "/todos/{todo_id}", response_model=AgendaTodo, summary="Change or tick a todo", responses=ERRORS
)
def update_todo(todo_id: UUID, request: TodoUpdate, context: AuthenticatedContext) -> AgendaTodo:
    return agenda_service.update_todo(context, todo_id, request)


@router.delete("/todos/{todo_id}", status_code=204, summary="Delete a todo", responses=ERRORS)
def delete_todo(todo_id: UUID, context: AuthenticatedContext) -> Response:
    agenda_service.delete_todo(context, todo_id)
    return Response(status_code=204)


@router.post(
    "/events",
    response_model=AgendaEvent,
    status_code=201,
    summary="Create an event",
    responses=ERRORS,
)
def create_event(request: EventRequest, context: AuthenticatedContext) -> AgendaEvent:
    return agenda_service.create_event(context, request)


@router.get("/events/{event_id}", response_model=AgendaEvent, summary="One event", responses=ERRORS)
def event(event_id: UUID, context: AuthenticatedContext) -> AgendaEvent:
    return agenda_service.event(context, event_id)


@router.patch(
    "/events/{event_id}", response_model=AgendaEvent, summary="Change an event", responses=ERRORS
)
def update_event(
    event_id: UUID, request: EventUpdate, context: AuthenticatedContext
) -> AgendaEvent:
    return agenda_service.update_event(context, event_id, request)


@router.delete("/events/{event_id}", status_code=204, summary="Cancel an event", responses=ERRORS)
def cancel_event(event_id: UUID, context: AuthenticatedContext) -> Response:
    agenda_service.cancel_event(context, event_id)
    return Response(status_code=204)


@router.post(
    "/events/{event_id}/respond",
    response_model=AgendaEvent,
    summary="Yes, No or Maybe",
    responses=ERRORS,
)
def respond(event_id: UUID, request: RespondRequest, context: AuthenticatedContext) -> AgendaEvent:
    return agenda_service.respond(context, event_id, request)
