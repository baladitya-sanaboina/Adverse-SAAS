"""Onboarding documents (owner request 2026-11-15).

/company/onboarding is Admin only. /public/onboarding/{token} is the private link a new client or
employee opens without signing in; the long random token is the only key, and it stops working
when it expires or the admin cancels it.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Request, Response

from app.middleware.authentication import AuthenticatedContext
from app.schemas.onboarding import (
    EmployeeDocumentsRequest,
    OnboardingOverview,
    PacketResponse,
    PublicPacket,
    PublicSubmit,
    TemplateRequest,
    TemplateResponse,
)
from app.schemas.registration import ErrorResponse
from app.services.onboarding_service import onboarding_service

router = APIRouter(prefix="/company/onboarding", tags=["onboarding"])
public_router = APIRouter(prefix="/public/onboarding", tags=["onboarding"])
ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Authentication is required."},
    403: {"model": ErrorResponse, "description": "Only the Company Admin."},
    404: {"model": ErrorResponse, "description": "Not found."},
    409: {"model": ErrorResponse, "description": "Not allowed now (e.g. after 60 hours)."},
    410: {"model": ErrorResponse, "description": "The link has expired."},
    422: {"model": ErrorResponse, "description": "Request validation failed."},
}


def _pdf(content: bytes, filename: str) -> Response:
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.get(
    "",
    response_model=OnboardingOverview,
    summary="Clients, employees and templates",
    responses=ERRORS,
)
def overview(context: AuthenticatedContext) -> OnboardingOverview:
    return onboarding_service.overview(context)


@router.post(
    "/clients/{client_id}",
    response_model=PacketResponse,
    summary="Send (or send again) a client's welcome, onboarding form and agreement",
    responses=ERRORS,
)
def send_client(client_id: UUID, context: AuthenticatedContext) -> PacketResponse:
    return onboarding_service.send_client(context, client_id)


@router.post(
    "/employees",
    response_model=PacketResponse,
    status_code=201,
    summary="Send an employee's offer, joining letter, welcome and agreement",
    responses=ERRORS,
)
def send_employee(
    request: EmployeeDocumentsRequest, context: AuthenticatedContext
) -> PacketResponse:
    return onboarding_service.send_employee(context, request)


@router.post(
    "/packets/{packet_id}/resend",
    response_model=PacketResponse,
    summary="Send again",
    responses=ERRORS,
)
def resend(packet_id: UUID, context: AuthenticatedContext) -> PacketResponse:
    return onboarding_service.resend(context, packet_id)


@router.post(
    "/packets/{packet_id}/cancel",
    response_model=PacketResponse,
    summary="Cancel the link",
    responses=ERRORS,
)
def cancel(packet_id: UUID, context: AuthenticatedContext) -> PacketResponse:
    return onboarding_service.cancel(context, packet_id)


@router.get("/packets/{packet_id}/pdf", summary="The documents as PDF", responses=ERRORS)
def packet_pdf(packet_id: UUID, context: AuthenticatedContext) -> Response:
    return _pdf(*onboarding_service.admin_pdf(context, packet_id))


@router.put(
    "/templates/{kind}",
    response_model=list[TemplateResponse],
    summary="Change a document's text",
    responses=ERRORS,
)
def save_template(
    kind: str, request: TemplateRequest, context: AuthenticatedContext
) -> list[TemplateResponse]:
    return onboarding_service.save_template(context, kind, request)


@router.delete(
    "/templates/{kind}",
    response_model=list[TemplateResponse],
    summary="Go back to the standard text",
    responses=ERRORS,
)
def reset_template(kind: str, context: AuthenticatedContext) -> list[TemplateResponse]:
    return onboarding_service.reset_template(context, kind)


@public_router.get(
    "/{token}", response_model=PublicPacket, summary="Open my documents", responses=ERRORS
)
def public_view(token: str) -> PublicPacket:
    return onboarding_service.public_view(token)


@public_router.post(
    "/{token}", response_model=PublicPacket, summary="Fill in and accept", responses=ERRORS
)
def public_submit(token: str, body: PublicSubmit, request: Request) -> PublicPacket:
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    ip = forwarded or (request.client.host if request.client else "")
    return onboarding_service.public_submit(token, body, ip, request.headers.get("user-agent", ""))


@public_router.get("/{token}/pdf", summary="My documents as PDF", responses=ERRORS)
def public_pdf(token: str) -> Response:
    return _pdf(*onboarding_service.public_pdf(token))
