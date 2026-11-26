"""Per-client access for managers and employees (owner request 2026-11-26)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.middleware.authentication import AuthenticatedContext
from app.schemas.production import (
    ClientAccessOverview,
    ClientAccessUpdate,
    MyClientAccessResponse,
)
from app.schemas.registration import ErrorResponse
from app.services.client_access_service import client_access_service

router = APIRouter(prefix="/company/client-access", tags=["client-access"])
staff_router = APIRouter(prefix="/workspace/client-access", tags=["workspace"])
ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Authentication is required."},
    403: {"model": ErrorResponse, "description": "Not available to your role."},
    404: {"model": ErrorResponse, "description": "The person or client was not found."},
    422: {"model": ErrorResponse, "description": "Request validation failed."},
}


@router.get(
    "",
    response_model=ClientAccessOverview,
    summary="Every manager and employee, every client, and who has which access",
    responses=ERRORS,
)
def overview(context: AuthenticatedContext) -> ClientAccessOverview:
    return client_access_service.overview(context)


@router.put(
    "",
    response_model=ClientAccessOverview,
    summary="Give, change or remove one person's access to one client",
    responses=ERRORS,
)
def update(context: AuthenticatedContext, request: ClientAccessUpdate) -> ClientAccessOverview:
    return client_access_service.update(context, request)


@staff_router.get(
    "",
    response_model=MyClientAccessResponse,
    summary="The clients I have access to, with my level",
    responses=ERRORS,
)
def mine(context: AuthenticatedContext) -> MyClientAccessResponse:
    return client_access_service.mine(context)
