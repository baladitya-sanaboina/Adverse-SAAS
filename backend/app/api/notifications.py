"""Notifications API and the live event stream (Phase 10)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

from app.middleware.authentication import AuthenticatedContext
from app.schemas.notifications import (
    MarkedReadResponse,
    NotificationListResponse,
    UnreadCountResponse,
)
from app.schemas.registration import ErrorResponse
from app.services import realtime
from app.services.notification_service import notification_service

router = APIRouter(prefix="/notifications", tags=["notifications"])
realtime_router = APIRouter(prefix="/realtime", tags=["notifications"])
ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Authentication is required."},
    403: {"model": ErrorResponse, "description": "A company workspace is required."},
}


@router.get(
    "",
    response_model=NotificationListResponse,
    summary="Own notifications, newest first",
    responses=ERRORS,
)
def list_notifications(
    context: AuthenticatedContext,
    limit: int = Query(30, ge=1, le=100),
    before: datetime | None = Query(None, description="Return notifications older than this."),
    unread: bool = Query(False, description="Only unread notifications."),
) -> NotificationListResponse:
    return notification_service.list(context, limit, before, unread)


@router.get(
    "/unread-count",
    response_model=UnreadCountResponse,
    summary="Number of unread notifications",
    responses=ERRORS,
)
def unread_count(context: AuthenticatedContext) -> UnreadCountResponse:
    return notification_service.unread_count(context)


@router.post(
    "/read-all",
    response_model=MarkedReadResponse,
    summary="Mark every notification as read",
    responses=ERRORS,
)
def read_all(context: AuthenticatedContext) -> MarkedReadResponse:
    return notification_service.mark_read(context, None)


@router.post(
    "/{notification_id}/read",
    response_model=MarkedReadResponse,
    summary="Mark one notification as read",
    responses=ERRORS,
)
def read_one(context: AuthenticatedContext, notification_id: UUID) -> MarkedReadResponse:
    return notification_service.mark_read(context, notification_id)


@realtime_router.get(
    "/stream",
    summary="Live events for the signed-in user (Server-Sent Events)",
    responses=ERRORS,
)
async def stream(request: Request, context: AuthenticatedContext) -> StreamingResponse:
    return StreamingResponse(
        realtime.stream(context.user_id, request.is_disconnected),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )
