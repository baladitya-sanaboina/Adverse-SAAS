"""Invoice and client billing shapes (Phase 11)."""

from datetime import date, datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.production import ClientBudgetSummary, ClientPaymentLine, Money, NamedRef

InvoiceStatus = Literal["DRAFT", "SENT", "PAID", "VOID"]


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
    deliveries: list[ClientDeliveryRow]
    days: list[ClientDayRow]
    payments: list[ClientPaymentLine]
    invoices: list[ClientInvoiceSummary]
