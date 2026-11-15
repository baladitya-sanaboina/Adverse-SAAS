"""Invoices (admin) and client billing (client portal), Phase 11.

Admin routes live under /company/invoices (not /company/finance/...) so they never collide with
the finance router's generic DELETE /company/finance/{kind}/{payment_id}.
"""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Query, Response

from app.middleware.authentication import AuthenticatedContext
from app.schemas.invoices import (
    BillingSettingsResponse,
    BudgetCycleResponse,
    ClientBillingResponse,
    ClientGstRequest,
    InvoiceCreateRequest,
    InvoiceDetailResponse,
    InvoiceListResponse,
    InvoicePreviewResponse,
    InvoiceSendResponse,
    InvoiceStatus,
    InvoiceUpdateRequest,
    PackageCreateRequest,
    PackageEndRequest,
    SheetEmailRequest,
    SheetEmailResponse,
    SheetInvoiceRequest,
)
from app.schemas.registration import ErrorResponse
from app.services.invoice_service import invoice_service

router = APIRouter(prefix="/company/invoices", tags=["invoices"])
client_router = APIRouter(prefix="/client-portal", tags=["client-portal"])
ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Authentication is required."},
    403: {
        "model": ErrorResponse,
        "description": "Finance permission or a client login is required.",
    },
    404: {"model": ErrorResponse, "description": "The invoice or client was not found."},
    409: {"model": ErrorResponse, "description": "The change is not allowed for this invoice."},
    422: {"model": ErrorResponse, "description": "Request validation failed."},
}


def _pdf(content: bytes, filename: str, download: bool) -> Response:
    disposition = "attachment" if download else "inline"
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'{disposition}; filename="{filename}"'},
    )


@router.get("", response_model=InvoiceListResponse, summary="List invoices", responses=ERRORS)
def list_invoices(
    context: AuthenticatedContext,
    client_id: UUID | None = None,
    status: InvoiceStatus | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> InvoiceListResponse:
    return invoice_service.list_invoices(context, client_id, status, page, page_size)


@router.get(
    "/cycles/{client_id}",
    response_model=list[BudgetCycleResponse],
    summary="A client's budget periods (one per top-up) with any invoice already made",
    responses=ERRORS,
)
def client_cycles(context: AuthenticatedContext, client_id: UUID) -> list[BudgetCycleResponse]:
    return invoice_service.cycles(context, client_id)


@router.get(
    "/preview",
    response_model=InvoicePreviewResponse,
    summary="Preview the work and total an invoice would have, without creating it",
    responses=ERRORS,
)
def preview_invoice(
    context: AuthenticatedContext, client_id: UUID, start: date, end: date
) -> InvoicePreviewResponse:
    return invoice_service.preview(context, client_id, start, end)


@router.post(
    "",
    response_model=InvoiceDetailResponse,
    status_code=201,
    summary="Create a draft invoice for a client and period",
    responses=ERRORS,
)
def create_invoice(
    context: AuthenticatedContext, request: InvoiceCreateRequest
) -> InvoiceDetailResponse:
    return invoice_service.create(context, request)


@router.post(
    "/sheet",
    response_model=InvoiceDetailResponse,
    status_code=201,
    summary="Make the invoice for one payment sheet (or open the one already made)",
    responses=ERRORS,
)
def create_sheet_invoice(
    context: AuthenticatedContext, request: SheetInvoiceRequest
) -> InvoiceDetailResponse:
    return invoice_service.create_for_sheet(context, request)


@router.post(
    "/sheet-email",
    response_model=SheetEmailResponse,
    summary="Email a payment sheet statement (client: email; manager: internal mail)",
    responses=ERRORS,
)
def email_sheet(context: AuthenticatedContext, request: SheetEmailRequest) -> SheetEmailResponse:
    return invoice_service.email_sheet(context, request)


@router.get(
    "/billing-settings/{client_id}",
    response_model=BillingSettingsResponse,
    summary="A client's GST and monthly packages",
    responses=ERRORS,
)
def billing_settings(context: AuthenticatedContext, client_id: UUID) -> BillingSettingsResponse:
    return invoice_service.billing_settings(context, client_id)


@router.put(
    "/billing-settings/{client_id}/gst",
    response_model=BillingSettingsResponse,
    summary="Switch GST on or off for a client",
    responses=ERRORS,
)
def set_gst(
    context: AuthenticatedContext, client_id: UUID, request: ClientGstRequest
) -> BillingSettingsResponse:
    return invoice_service.set_gst(context, client_id, request)


@router.post(
    "/billing-settings/{client_id}/packages",
    response_model=BillingSettingsResponse,
    status_code=201,
    summary="Start a monthly package",
    responses=ERRORS,
)
def add_package(
    context: AuthenticatedContext, client_id: UUID, request: PackageCreateRequest
) -> BillingSettingsResponse:
    return invoice_service.add_package(context, client_id, request)


@router.post(
    "/billing-settings/{client_id}/packages/{package_id}/end",
    response_model=BillingSettingsResponse,
    summary="End a monthly package on a date",
    responses=ERRORS,
)
def end_package(
    context: AuthenticatedContext, client_id: UUID, package_id: UUID, request: PackageEndRequest
) -> BillingSettingsResponse:
    return invoice_service.end_package(context, client_id, package_id, request)


@router.delete(
    "/billing-settings/{client_id}/packages/{package_id}",
    response_model=BillingSettingsResponse,
    summary="Remove a package that has not started",
    responses=ERRORS,
)
def remove_package(
    context: AuthenticatedContext, client_id: UUID, package_id: UUID
) -> BillingSettingsResponse:
    return invoice_service.remove_package(context, client_id, package_id)


@router.get(
    "/{invoice_id}", response_model=InvoiceDetailResponse, summary="Invoice", responses=ERRORS
)
def get_invoice(context: AuthenticatedContext, invoice_id: UUID) -> InvoiceDetailResponse:
    return invoice_service.get(context, invoice_id)


@router.patch(
    "/{invoice_id}",
    response_model=InvoiceDetailResponse,
    summary="Mark paid or void, or change notes and due date",
    responses=ERRORS,
)
def update_invoice(
    context: AuthenticatedContext, invoice_id: UUID, request: InvoiceUpdateRequest
) -> InvoiceDetailResponse:
    return invoice_service.update(context, invoice_id, request)


@router.delete("/{invoice_id}", status_code=204, summary="Delete a draft invoice", responses=ERRORS)
def delete_invoice(context: AuthenticatedContext, invoice_id: UUID) -> Response:
    invoice_service.delete(context, invoice_id)
    return Response(status_code=204)


@router.post(
    "/{invoice_id}/send",
    response_model=InvoiceSendResponse,
    summary="Email the invoice PDF to the client and publish it in the client portal",
    responses=ERRORS,
)
def send_invoice(context: AuthenticatedContext, invoice_id: UUID) -> InvoiceSendResponse:
    return invoice_service.send(context, invoice_id)


@router.get("/{invoice_id}/pdf", summary="Invoice PDF", responses=ERRORS)
def invoice_pdf(
    context: AuthenticatedContext, invoice_id: UUID, download: bool = False
) -> Response:
    content, filename = invoice_service.pdf(context, invoice_id)
    return _pdf(content, filename, download)


@client_router.get(
    "/billing",
    response_model=ClientBillingResponse,
    summary="Client's own budget periods, delivered work with running budget, payments, invoices",
    responses=ERRORS,
)
def client_billing(context: AuthenticatedContext) -> ClientBillingResponse:
    return invoice_service.client_billing(context)


@client_router.get(
    "/invoices/{invoice_id}/pdf", summary="Client's own sent invoice as PDF", responses=ERRORS
)
def client_invoice_pdf(
    context: AuthenticatedContext, invoice_id: UUID, download: bool = False
) -> Response:
    content, filename = invoice_service.client_pdf(context, invoice_id)
    return _pdf(content, filename, download)
