"""Web Push subscriptions (owner request 2026-11-15)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request, Response

from app.middleware.authentication import AuthenticatedContext
from app.schemas.push import PushKeyResponse, PushSubscribeRequest, PushUnsubscribeRequest
from app.schemas.registration import ErrorResponse
from app.services.push_service import push_service

router = APIRouter(prefix="/push", tags=["notifications"])
ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Authentication is required."},
    409: {"model": ErrorResponse, "description": "Push is not set up on this server."},
    422: {"model": ErrorResponse, "description": "Request validation failed."},
}


@router.get(
    "/key",
    response_model=PushKeyResponse,
    summary="The key browsers subscribe with",
    responses=ERRORS,
)
def key(context: AuthenticatedContext) -> PushKeyResponse:
    return push_service.key()


@router.post(
    "/subscribe", status_code=204, summary="Turn on push for this browser", responses=ERRORS
)
def subscribe(
    request: PushSubscribeRequest, http: Request, context: AuthenticatedContext
) -> Response:
    push_service.subscribe(context, request, http.headers.get("user-agent", ""))
    return Response(status_code=204)


@router.post(
    "/unsubscribe", status_code=204, summary="Turn off push for this browser", responses=ERRORS
)
def unsubscribe(request: PushUnsubscribeRequest, context: AuthenticatedContext) -> Response:
    push_service.unsubscribe(context, request.endpoint)
    return Response(status_code=204)
