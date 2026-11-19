"""Invoice and client billing shapes (Phase 11)."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.production import (
    ClientBudgetSummary,
    ClientPaymentLine,
    Money,
    NamedRef,
    SheetLine,
)

InvoiceStatus = Literal["DRAFT", "SENT", "PAID", "VOID"]


# -- payment sheets overview (owner request 2026-11-14) ------------------------------------

SheetStatus = Literal["OVER", "USED_UP", "NEAR", "OK"]


class PaymentSheet(BaseModel):
    """One payment sheet, the same shape for a manager top-up and a client budget top-up."""

    index: int
    start: date
    end: date | None
    paid: Money
    carried_in: Money
    used: Money
    left: Money
    items: int
    ran_out_on: date | None
    lines: list[SheetLine]
    # Admin views only: the invoice made for this sheet, if any (owner request 2026-11-15).
    invoice_id: UUID | None = None
    invoice_code: str | None = None
    invoice_status: str | None = None


class SheetOwner(BaseModel):
    """A manager or client with their sheets; status is about the current (open) sheet."""

    kind: Literal["MANAGER", "CLIENT"]
    id: UUID
    name: str
    code: str
    status: SheetStatus
    left: Money
    pot: Money
    percent_used: float
    ran_out_on: date | None
    sheets: list[PaymentSheet]


class SheetsOverviewResponse(BaseModel):
    currency: str
    managers: list[SheetOwner]
    clients: list[SheetOwner]


class InvoiceCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_id: UUID
    period_start: date
    period_end: date
    due_date: date | None = None
    notes: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def period_in_order(self) -> Self:
        if self.period_end < self.period_start:
            raise ValueError("The end date must be on or after the start date.")
        return self


class InvoiceUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["PAID", "VOID", "SENT"] | None = None
    notes: str | None = Field(default=None, max_length=1000)
    due_date: date | None = None


class InvoiceLineResponse(BaseModel):
    position: int
    delivered_on: date
    title: str
    service_name: str
    amount: Money


class InvoicePaymentResponse(BaseModel):
    received_on: date
    method: str
    reference: str
    amount: Money


class InvoiceResponse(BaseModel):
    id: UUID
    code: str
    number: int
    status: InvoiceStatus
    source: str
    client: NamedRef
    client_email: str | None
    period_start: date
    period_end: date
    issue_date: date
    due_date: date | None
    currency: str
    subtotal: Money
    tax_rate: Decimal = Decimal("0")
    tax_amount: Money = Decimal("0.00")
    total: Money = Decimal("0.00")
    client_gstin: str = ""
    payments_total: Money
    budget_added: Money
    balance: Money
    items: int
    notes: str
    created_by_name: str
    sent_at: datetime | None
    paid_at: datetime | None
    created_at: datetime


class InvoiceDetailResponse(InvoiceResponse):
    lines: list[InvoiceLineResponse]
    payments: list[InvoicePaymentResponse]


class InvoicePreviewResponse(BaseModel):
    """What an invoice would contain, shown before it is created."""

    period_start: date
    period_end: date
    currency: str
    items: int
    subtotal: Money
    tax_rate: Decimal = Decimal("0")
    tax_amount: Money = Decimal("0.00")
    total: Money = Decimal("0.00")
    payments_total: Money
    budget_added: Money
    lines: list[InvoiceLineResponse]


class InvoiceSendResponse(BaseModel):
    invoice: InvoiceDetailResponse
    emailed: bool
    message: str


class InvoiceListResponse(BaseModel):
    items: list[InvoiceResponse]
    page: int
    page_size: int
    total: int
    total_pages: int


class BudgetCycleResponse(BaseModel):
    index: int
    start: date
    end: date | None
    amount: Money
    used: Money
    remaining: Money
    items: int
    invoice_id: UUID | None = None
    invoice_code: str | None = None
    # Payment sheets (owner decision 2026-11-14): balance carried in from the previous sheet,
    # the day the money ran out, and the sheet's own lines.
    carried_in: Money = Decimal("0.00")
    ran_out_on: date | None = None
    lines: list[SheetLine] = []


class ClientDeliveryRow(BaseModel):
    delivered_on: date
    title: str
    service_name: str
    amount: Money
    budget_left: Money


class ClientDayRow(BaseModel):
    day: date
    items: int
    amount: Money
    budget_left: Money


class ClientInvoiceSummary(BaseModel):
    id: UUID
    code: str
    status: InvoiceStatus
    period_start: date
    period_end: date
    issue_date: date
    subtotal: Money
    tax_amount: Money = Decimal("0.00")
    total: Money = Decimal("0.00")
    payments_total: Money
    balance: Money
    items: int


class ClientBillingResponse(BaseModel):
    client_name: str
    currency: str
    budget: ClientBudgetSummary
    total_charged: Money
    total_paid: Money
    pending_amount: Money
    current_month_charged: Money
    cycles: list[BudgetCycleResponse]
    # Payment sheets: one per payment received from the client (owner decision 2026-11-14).
    sheets: list[PaymentSheet] = []
    deliveries: list[ClientDeliveryRow]
    days: list[ClientDayRow]
    payments: list[ClientPaymentLine]
    invoices: list[ClientInvoiceSummary]


# -- GST and monthly packages per client (owner requests 2026-11-15) ----------------------------


class SheetInvoiceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_id: UUID
    start: date
    # Which sheet: two top-ups on one day make two sheets with the same start (2026-11-19).
    index: int | None = None


class ClientGstRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gst_enabled: bool
    gst_rate: Decimal = Field(default=Decimal("18"), ge=0, le=100, decimal_places=2)
    gstin: str = Field(default="", max_length=20, pattern=r"^[0-9A-Za-z]*$")


class PackageCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=120)
    monthly_price: Decimal = Field(ge=0, le=Decimal("99999999.99"), decimal_places=2)
    videos_included: int = Field(ge=0, le=1000)
    starts_on: date


class PackageEndRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ends_on: date


class PackageResponse(BaseModel):
    id: UUID
    name: str
    monthly_price: Money
    videos_included: int
    starts_on: date
    ends_on: date | None
    status: Literal["UPCOMING", "ACTIVE", "ENDED"]
    used_this_month: int
    created_by_name: str


class BillingSettingsResponse(BaseModel):
    client_id: UUID
    currency: str
    gst_enabled: bool
    gst_rate: Decimal
    gstin: str
    company_gstin: str
    packages: list[PackageResponse]


class SheetEmailRequest(BaseModel):
    """Email one payment sheet's statement (owner request 2026-11-15)."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["MANAGER", "CLIENT"]
    owner_id: UUID
    index: int = Field(ge=1)


class SheetEmailResponse(BaseModel):
    sent_to: str
    message: str
