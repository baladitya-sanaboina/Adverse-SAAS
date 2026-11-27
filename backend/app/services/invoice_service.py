"""Client invoices and the client billing view (Phase 11).

An invoice is a snapshot of the work a client received in a period (usually one budget top-up)
plus the payments received in that period. No tax for now (owner decision 2026-11-14).
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from app.core.settings import settings
from app.repositories.finance_repository import FinanceRepository
from app.repositories.invoice_repository import InvoiceRepository, InvoiceRow
from app.repositories.package_repository import PackageRepository, PackageRow
from app.repositories.task_repository import TaskRepository
from app.schemas.authentication import AuthContext
from app.schemas.invoices import (
    BillingSettingsResponse,
    BudgetCycleResponse,
    ClientBillingResponse,
    ClientDayRow,
    ClientDeliveryRow,
    ClientGstRequest,
    ClientInvoiceSummary,
    InvoiceCreateRequest,
    InvoiceDetailResponse,
    InvoiceLineResponse,
    InvoiceListResponse,
    InvoicePaymentResponse,
    InvoicePreviewResponse,
    InvoiceResponse,
    InvoiceSendResponse,
    InvoiceUpdateRequest,
    PackageCreateRequest,
    PackageEndRequest,
    PackageResponse,
    PaymentSheet,
    SheetEmailRequest,
    SheetEmailResponse,
    SheetInvoiceRequest,
    SheetOwner,
    SheetsOverviewResponse,
    SheetStatus,
)
from app.schemas.production import (
    ClientBudgetSummary,
    ClientPaymentLine,
    NamedRef,
    SheetLine,
    WalletPeriod,
)
from app.services.authentication_service import AuthenticationError
from app.services.finance_service import finance_service
from app.services.invoice_pdf import amount_text, render_invoice_pdf, render_sheet_statement_pdf
from app.services.notification_service import notification_service
from app.services.permission_service import validate_user_action_access
from app.services.production_rules import (
    PAYMENT_METHOD_TEXT,
    BudgetCycle,
    budget_cycles,
    daily_summary,
    entry_time,
    money,
    resolve_period,
    running_budget_left,
)

logger = logging.getLogger(__name__)

# A sheet counts as running low once this much of it is used (owner request 2026-11-14).
SHEET_NEAR_PERCENT = 80
ZERO = Decimal("0")


def _pages(total: int, size: int) -> int:
    return max(1, (total + size - 1) // size)


def _period_sheet(period: WalletPeriod) -> PaymentSheet:
    """A manager's top-up period in the shared payment sheet shape."""
    return PaymentSheet(
        index=period.index,
        start=period.start,
        end=period.end,
        paid=period.topped_up,
        carried_in=period.carried_in,
        used=period.earned,
        left=period.balance,
        items=period.items,
        ran_out_on=period.ran_out_on,
        lines=period.lines,
    )


def _balance(row: InvoiceRow) -> Decimal:
    """Above zero: still to pay. Below zero: budget left (2026-11-28, was called credit)."""
    return money(row.total - Decimal(row.payments_total) - Decimal(row.carried_in))


def _balance_line(row: InvoiceRow) -> tuple[str, str]:
    """The invoice's closing line for mails: budget left, or the amount due when it ran over."""
    balance = _balance(row)
    if balance > 0:
        return "Amount due", amount_text(balance, row.currency)
    return "Budget left", amount_text(-balance, row.currency)


def _sheet(cycle: BudgetCycle, invoice: InvoiceRow | None = None) -> PaymentSheet:
    return PaymentSheet(
        index=cycle.index,
        start=cycle.start,
        end=cycle.end,
        paid=cycle.amount,
        carried_in=cycle.carried_in,
        used=cycle.used,
        left=cycle.remaining,
        items=cycle.items,
        ran_out_on=cycle.ran_out_on,
        lines=[
            SheetLine(
                day=line.day,
                kind=line.kind,
                label=line.label,
                amount=line.amount,
                balance=line.balance,
            )
            for line in cycle.lines
        ],
        invoice_id=invoice.id if invoice else None,
        invoice_code=invoice.code if invoice else None,
        invoice_status=invoice.status if invoice else None,
    )


def _budget(sheets: list[PaymentSheet]) -> ClientBudgetSummary:
    paid = money(sum((Decimal(sheet.paid) for sheet in sheets), ZERO))
    used = money(sum((Decimal(sheet.used) for sheet in sheets), ZERO))
    left = money(Decimal(sheets[-1].left)) if sheets else ZERO
    return ClientBudgetSummary(
        has_budget=paid > 0,
        total=paid,
        used=used,
        remaining=max(left, ZERO),
        overage=max(-left, ZERO),
    )


class InvoiceService:
    def __init__(
        self,
        repository: InvoiceRepository | None = None,
        finance: FinanceRepository | None = None,
        tasks: TaskRepository | None = None,
        packages: PackageRepository | None = None,
    ):
        self.repository = repository or InvoiceRepository()
        self.finance = finance or FinanceRepository()
        self.tasks = tasks or TaskRepository()
        self.packages = packages or PackageRepository()

    # -- access and helpers ----------------------------------------------------------------

    @staticmethod
    def _admin(context: AuthContext, action: str) -> UUID:
        if context.role != "COMPANY_ADMIN" or context.company_id is None:
            raise AuthenticationError(
                403, "COMPANY_ADMIN_REQUIRED", "Only the Company Admin can manage invoices."
            )
        if not validate_user_action_access(str(context.user_id), context.role, "FINANCE", action):
            raise AuthenticationError(
                403,
                f"FINANCE_{action}_REQUIRED",
                f"Finance {action.lower()} permission is required.",
            )
        return context.company_id

    def _client_of(self, context: AuthContext) -> tuple[UUID, NamedRef]:
        if context.role != "COMPANY_CLIENT" or context.company_id is None:
            raise AuthenticationError(403, "CLIENT_REQUIRED", "Only client accounts have billing.")
        client = self.tasks.get_client_for_user(context.company_id, context.user_id)
        if client is None:
            raise AuthenticationError(
                404,
                "CLIENT_PROFILE_NOT_LINKED",
                "This login is not linked to a client profile yet. Please contact the agency.",
            )
        return context.company_id, NamedRef(id=client.id, name=client.name, code=client.code)

    def _zone(self, company_id: UUID) -> tuple[str, ZoneInfo, date]:
        name = self.finance.company_timezone(company_id)
        try:
            zone = ZoneInfo(name)
        except Exception:  # noqa: BLE001
            name, zone = "UTC", ZoneInfo("UTC")
        return name, zone, datetime.now(zone).date()

    @staticmethod
    def _local(moment: datetime, zone: ZoneInfo) -> date:
        aware = moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)
        return aware.astimezone(zone).date()

    def _budget_entries(
        self, company_id: UUID, client_id: UUID, zone: ZoneInfo
    ) -> list[tuple[date, str, Decimal]]:
        return [
            (self._local(entry.created_at, zone), entry.type, Decimal(entry.amount))
            for entry in self.finance.list_budget_entries(company_id, client_id)
        ]

    def _cycles(
        self, company_id: UUID, client_id: UUID
    ) -> tuple[list[BudgetCycleResponse], list[tuple[date, Decimal]]]:
        tz, zone, _ = self._zone(company_id)
        entries = self._budget_entries(company_id, client_id, zone)
        rows = list(reversed(self.finance.client_deliveries(company_id, client_id, tz)))
        deliveries = [(row.delivered_on, Decimal(row.amount)) for row in rows]
        cycles = budget_cycles(
            entries,
            [
                (
                    row.delivered_on,
                    Decimal(row.amount),
                    row.title if row.kind == "PACKAGE" else f"{row.title} · {row.service_name}",
                    row.kind == "WORK",
                )
                for row in rows
            ],
        )
        invoices, _ = self.repository.list(company_id, client_id, ["DRAFT", "SENT", "PAID"], 1, 100)
        by_start = {row.period_start: row for row in invoices if row.source == "TOP_UP"}
        return [
            BudgetCycleResponse(
                index=cycle.index,
                start=cycle.start,
                end=cycle.end,
                amount=cycle.amount,
                used=cycle.used,
                remaining=cycle.remaining,
                items=cycle.items,
                invoice_id=by_start[cycle.start].id if cycle.start in by_start else None,
                invoice_code=by_start[cycle.start].code if cycle.start in by_start else None,
                carried_in=cycle.carried_in,
                ran_out_on=cycle.ran_out_on,
                lines=[
                    SheetLine(
                        day=line.day,
                        kind=line.kind,
                        label=line.label,
                        amount=line.amount,
                        balance=line.balance,
                    )
                    for line in cycle.lines
                ],
            )
            for cycle in cycles
        ], deliveries

    @staticmethod
    def _response(row: InvoiceRow) -> InvoiceResponse:
        return InvoiceResponse(
            id=row.id,
            code=row.code,
            number=row.number,
            status=row.status,
            source=row.source,
            client=NamedRef(id=row.client_id, name=row.client_name, code=row.client_code),
            client_email=row.client_email,
            period_start=row.period_start,
            period_end=row.period_end,
            issue_date=row.issue_date,
            due_date=row.due_date,
            currency=row.currency,
            subtotal=money(row.subtotal),
            tax_rate=Decimal(row.tax_rate),
            tax_amount=money(row.tax_amount),
            total=money(row.total),
            client_gstin=row.client_gstin,
            payments_total=money(row.payments_total),
            budget_added=money(row.budget_added),
            carried_in=money(row.carried_in),
            sheet_index=row.sheet_index,
            balance=_balance(row),
            items=row.line_count,
            notes=row.notes,
            created_by_name=row.created_by_name,
            sent_at=row.sent_at,
            paid_at=row.paid_at,
            created_at=row.created_at,
        )

    def _detail(self, company_id: UUID, invoice_id: UUID) -> InvoiceDetailResponse:
        row = self.repository.get(company_id, invoice_id)
        if row is None:
            raise AuthenticationError(404, "INVOICE_NOT_FOUND", "Invoice was not found.")
        return InvoiceDetailResponse(
            **self._response(row).model_dump(),
            lines=[
                InvoiceLineResponse(
                    position=line.position,
                    delivered_on=line.delivered_on,
                    title=line.title,
                    service_name=line.service_name,
                    amount=money(line.amount),
                )
                for line in self.repository.lines(row.id)
            ],
            payments=[
                InvoicePaymentResponse(
                    received_on=date.fromisoformat(str(item["received_on"])[:10]),
                    method=str(item.get("method", "")),
                    reference=str(item.get("reference", "")),
                    amount=money(Decimal(str(item.get("amount", "0")))),
                )
                for item in row.payments
            ],
        )

    def _collect(
        self, company_id: UUID, client_id: UUID, start: date, end: date
    ) -> tuple[list[Any], list[Any], Decimal]:
        """Delivered work (oldest first), payments and budget added in the period."""
        tz, zone, _ = self._zone(company_id)
        deliveries = list(
            reversed(self.finance.client_deliveries(company_id, client_id, tz, start, end))
        )
        payments = [
            payment
            for payment in self.finance.list_client_payments_for_client(company_id, client_id)
            if start <= payment.received_on <= end
        ]
        budget_added = sum(
            (
                amount
                for day, kind, amount in self._budget_entries(company_id, client_id, zone)
                if kind in ("INITIAL", "TOP_UP") and start <= day <= end
            ),
            ZERO,
        )
        return deliveries, payments, budget_added

    def _tax(
        self, company_id: UUID, client_id: UUID, subtotal: Decimal
    ) -> tuple[Decimal, Decimal, str]:
        """GST for this client (owner request 2026-11-15): (rate, amount, client GSTIN)."""
        tax = self.packages.client_tax(company_id, client_id)
        if tax is None or not tax.gst_enabled:
            return ZERO, money(ZERO), tax.gstin if tax else ""
        return Decimal(tax.gst_rate), money(subtotal * Decimal(tax.gst_rate) / 100), tax.gstin

    def _opening_balance(self, company_id: UUID, client_id: UUID, start: date) -> Decimal:
        """Budget left (+) or extra used (-) before `start`: payments minus work delivered."""
        tz, _, _ = self._zone(company_id)
        paid = sum(
            (
                Decimal(payment.amount)
                for payment in self.finance.list_client_payments_for_client(company_id, client_id)
                if payment.received_on < start
            ),
            ZERO,
        )
        used = sum(
            (
                Decimal(row.amount)
                for row in self.finance.client_deliveries(company_id, client_id, tz)
                if row.delivered_on < start
            ),
            ZERO,
        )
        return money(paid - used)

    def _make(
        self,
        company_id: UUID,
        client_id: UUID,
        actor_id: UUID,
        start: date,
        end: date,
        source: str,
        due_date: date | None = None,
        notes: str = "",
    ) -> UUID:
        """An invoice for a date range, opening with the budget left before it."""
        deliveries, payments, budget_added = self._collect(company_id, client_id, start, end)
        return self._save(
            company_id,
            client_id,
            actor_id,
            start,
            end,
            source,
            deliveries,
            payments,
            budget_added,
            carried_in=self._opening_balance(company_id, client_id, start),
            due_date=due_date,
            notes=notes,
        )

    def _make_for_sheet(
        self,
        company_id: UUID,
        client_id: UUID,
        actor_id: UUID,
        cycle: BudgetCycle,
        payments: list[Any],
        rows: list[Any],
    ) -> UUID:
        """The invoice of one payment sheet: exactly its payment and its work (two payments on
        the same day are two sheets with two invoices), opening with what the sheet before left."""
        _, _, today = self._zone(company_id)
        start, end = cycle.start, cycle.end or min(cycle.ran_out_on or today, today)
        return self._save(
            company_id,
            client_id,
            actor_id,
            start,
            max(end, start),
            "SHEET",
            [rows[position] for position in cycle.delivery_indexes],
            [payments[cycle.entry_index]] if cycle.entry_index is not None else [],
            ZERO,
            carried_in=cycle.carried_in,
            sheet_index=cycle.index,
        )

    def _save(
        self,
        company_id: UUID,
        client_id: UUID,
        actor_id: UUID,
        start: date,
        end: date,
        source: str,
        deliveries: list[Any],
        payments: list[Any],
        budget_added: Decimal,
        *,
        carried_in: Decimal = ZERO,
        sheet_index: int | None = None,
        due_date: date | None = None,
        notes: str = "",
    ) -> UUID:
        _, _, today = self._zone(company_id)
        subtotal = money(sum((Decimal(row.amount) for row in deliveries), ZERO))
        tax_rate, tax_amount, gstin = self._tax(company_id, client_id, subtotal)
        return self.repository.create(
            company_id,
            client_id,
            actor_id,
            {
                "source": source,
                "period_start": start,
                "period_end": end,
                "issue_date": today,
                "due_date": due_date,
                "currency": self.finance.company_currency(company_id),
                "subtotal": subtotal,
                "tax_rate": tax_rate,
                "tax_amount": tax_amount,
                "client_gstin": gstin,
                "payments_total": money(sum((Decimal(p.amount) for p in payments), ZERO)),
                "budget_added": money(budget_added),
                "carried_in": money(carried_in),
                "sheet_index": sheet_index,
                "payments": [
                    {
                        "received_on": payment.received_on.isoformat(),
                        "method": payment.method,
                        "reference": payment.reference,
                        "amount": str(money(payment.amount)),
                    }
                    for payment in sorted(payments, key=lambda item: item.received_on)
                ],
                "notes": notes,
            },
            [
                {
                    "task_id": row.task_id,
                    "delivered_on": row.delivered_on,
                    "title": row.title,
                    "service_name": row.service_name,
                    "amount": money(row.amount),
                }
                for row in deliveries
            ],
        )

    # -- admin ----------------------------------------------------------------------------

    def list_invoices(
        self,
        context: AuthContext,
        client_id: UUID | None,
        status: str | None,
        page: int,
        page_size: int,
    ) -> InvoiceListResponse:
        company_id = self._admin(context, "VIEW")
        rows, total = self.repository.list(
            company_id, client_id, [status] if status else None, page, page_size
        )
        return InvoiceListResponse(
            items=[self._response(row) for row in rows],
            page=page,
            page_size=page_size,
            total=total,
            total_pages=_pages(total, page_size),
        )

    def cycles(self, context: AuthContext, client_id: UUID) -> list[BudgetCycleResponse]:
        company_id = self._admin(context, "VIEW")
        if self.tasks.get_client(company_id, client_id) is None:
            raise AuthenticationError(404, "CLIENT_NOT_FOUND", "Client was not found.")
        return self._cycles(company_id, client_id)[0]

    def preview(
        self, context: AuthContext, client_id: UUID, start: date, end: date
    ) -> InvoicePreviewResponse:
        """What an invoice for this client and period would contain, without saving it."""
        company_id = self._admin(context, "VIEW")
        if end < start:
            raise AuthenticationError(
                422, "INVALID_PERIOD", "The end date must be on or after the start date."
            )
        if self.tasks.get_client(company_id, client_id) is None:
            raise AuthenticationError(404, "CLIENT_NOT_FOUND", "Client was not found.")
        deliveries, payments, budget_added = self._collect(company_id, client_id, start, end)
        subtotal = money(sum((Decimal(row.amount) for row in deliveries), ZERO))
        paid = money(sum((Decimal(p.amount) for p in payments), ZERO))
        tax_rate, tax_amount, _ = self._tax(company_id, client_id, subtotal)
        return InvoicePreviewResponse(
            period_start=start,
            period_end=end,
            currency=self.finance.company_currency(company_id),
            items=len(deliveries),
            subtotal=subtotal,
            tax_rate=tax_rate,
            tax_amount=tax_amount,
            total=money(subtotal + tax_amount),
            payments_total=paid,
            budget_added=money(budget_added),
            carried_in=self._opening_balance(company_id, client_id, start),
            lines=[
                InvoiceLineResponse(
                    position=index,
                    delivered_on=row.delivered_on,
                    title=row.title,
                    service_name=row.service_name,
                    amount=money(row.amount),
                )
                for index, row in enumerate(deliveries, start=1)
            ],
        )

    def create(self, context: AuthContext, request: InvoiceCreateRequest) -> InvoiceDetailResponse:
        company_id = self._admin(context, "CREATE")
        if self.tasks.get_client(company_id, request.client_id) is None:
            raise AuthenticationError(404, "CLIENT_NOT_FOUND", "Client was not found.")
        invoice_id = self._make(
            company_id,
            request.client_id,
            context.user_id,
            request.period_start,
            request.period_end,
            "MANUAL",
            request.due_date,
            request.notes.strip(),
        )
        return self._detail(company_id, invoice_id)

    def get(self, context: AuthContext, invoice_id: UUID) -> InvoiceDetailResponse:
        return self._detail(self._admin(context, "VIEW"), invoice_id)

    def update(
        self, context: AuthContext, invoice_id: UUID, request: InvoiceUpdateRequest
    ) -> InvoiceDetailResponse:
        company_id = self._admin(context, "EDIT")
        row = self.repository.get(company_id, invoice_id)
        if row is None:
            raise AuthenticationError(404, "INVOICE_NOT_FOUND", "Invoice was not found.")
        if row.status == "VOID":
            raise AuthenticationError(409, "INVOICE_VOID", "A void invoice cannot be changed.")
        changes: dict[str, object] = {}
        if request.notes is not None:
            changes["notes"] = request.notes.strip()
        if "due_date" in request.model_fields_set:
            changes["due_date"] = request.due_date
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if request.status == "PAID":
            changes.update(status="PAID", paid_at=now)
        elif request.status == "VOID":
            changes["status"] = "VOID"
        elif request.status == "SENT" and row.status == "PAID":
            changes.update(status="SENT", paid_at=None)
        self.repository.update(company_id, invoice_id, changes)
        return self._detail(company_id, invoice_id)

    def delete(self, context: AuthContext, invoice_id: UUID) -> None:
        company_id = self._admin(context, "DELETE")
        if not self.repository.delete_draft(company_id, invoice_id):
            raise AuthenticationError(
                409,
                "INVOICE_NOT_DRAFT",
                "Only draft invoices can be deleted. Mark a sent invoice as void instead.",
            )

    def pdf(self, context: AuthContext, invoice_id: UUID) -> tuple[bytes, str]:
        company_id = self._admin(context, "VIEW")
        return self._pdf(company_id, invoice_id)

    def _pdf(self, company_id: UUID, invoice_id: UUID) -> tuple[bytes, str]:
        row = self.repository.get(company_id, invoice_id)
        if row is None:
            raise AuthenticationError(404, "INVOICE_NOT_FOUND", "Invoice was not found.")
        content = render_invoice_pdf(
            row, self.repository.lines(row.id), self.repository.company_profile(company_id)
        )
        return content, f"{row.code}.pdf"

    def _invoice_to_mailbox(self, company_id: UUID, row: InvoiceRow, company: str) -> None:
        """The invoice also lands in the client's internal mailbox (owner request 2026-11-19)."""
        try:
            from app.services.mail_service import mail_card, mail_service

            client_user = notification_service.client_user(company_id, row.client_id)
            if client_user is None:
                return
            period = f"{row.period_start:%d %b %Y} – {row.period_end:%d %b %Y}"
            amount = amount_text(row.total, row.currency)
            label, value = _balance_line(row)
            lines = self.repository.lines(row.id)
            table = [["Date", "Work", "Amount"]] + [
                [
                    f"{line.delivered_on:%d %b %Y}",
                    line.title,
                    amount_text(line.amount, row.currency),
                ]
                for line in lines
            ]
            mail_service.system(
                company_id,
                [client_user],
                f"Invoice {row.code} from {company}",
                f"Your invoice {row.code} for {period} is ready: {amount}. {label}: {value}.",
                "/billing",
                "PAYMENT",
                once_key=f"invoice-box:{row.id}",
                card=mail_card(
                    f"Invoice {row.code}",
                    [
                        f"Hello {row.client_name}, your invoice for the work delivered {period} is ready."
                    ],
                    rows=[
                        ("Invoice", row.code),
                        ("Period", period),
                        ("Work delivered", amount),
                        (label, value),
                    ],
                    table=table if lines else [],
                    action="Open billing",
                    note="The PDF is attached to the mail sent to your Gmail and can be downloaded from Billing.",
                ),
            )
        except Exception:  # noqa: BLE001
            logger.warning("Invoice mailbox copy failed", exc_info=True)

    def send(self, context: AuthContext, invoice_id: UUID) -> InvoiceSendResponse:
        company_id = self._admin(context, "EDIT")
        row = self.repository.get(company_id, invoice_id)
        if row is None:
            raise AuthenticationError(404, "INVOICE_NOT_FOUND", "Invoice was not found.")
        if row.status == "VOID":
            raise AuthenticationError(409, "INVOICE_VOID", "A void invoice cannot be sent.")
        content, filename = self._pdf(company_id, invoice_id)
        company = self.repository.company_profile(company_id)
        email = self.repository.client_login_email(company_id, row.client_id)
        emailed, message = False, "No email address on file; the invoice is in the client portal."
        if email:
            try:
                from app.services.email_service import email_service

                email_service.send_invoice(
                    email,
                    company_name=company.name,
                    client_name=row.client_name,
                    invoice_code=row.code,
                    amount=amount_text(row.total, row.currency),
                    period=f"{row.period_start:%d %b %Y} – {row.period_end:%d %b %Y}",
                    portal_url=_portal_url(),
                    pdf=content,
                    filename=filename,
                    balance=_balance_line(row),
                )
                emailed, message = True, f"Emailed to {email}."
            except Exception:  # noqa: BLE001 - the invoice is still available in the portal
                logger.warning("Invoice email failed", exc_info=True)
                message = "The email could not be sent; the invoice is in the client portal."
        self._invoice_to_mailbox(company_id, row, company.name)
        if row.status == "DRAFT":
            self.repository.update(
                company_id,
                invoice_id,
                {"status": "SENT", "sent_at": datetime.now(timezone.utc).replace(tzinfo=None)},
            )
        notification_service.notify(
            company_id,
            [notification_service.client_user(company_id, row.client_id)],
            "invoice.sent",
            f"New invoice {row.code}",
            f"{amount_text(row.total, row.currency)} for "
            f"{row.period_start:%d %b} – {row.period_end:%d %b %Y}.",
            "/billing",
            {"invoice_id": str(row.id)},
        )
        return InvoiceSendResponse(
            invoice=self._detail(company_id, invoice_id), emailed=emailed, message=message
        )

    def create_for_used_up_budget(self, company_id: UUID, client_id: UUID, actor_id: UUID) -> None:
        """Kept for callers of Phase 11; invoices now follow payment sheets."""
        self.ensure_sheet_invoices(company_id, client_id, actor_id)

    # -- invoices per payment sheet (owner request 2026-11-15) --------------------------------

    def _sheet_invoices(
        self, company_id: UUID, client_id: UUID, cycles: list[BudgetCycle]
    ) -> dict[int, InvoiceRow]:
        """Each payment sheet's invoice, by sheet number (2026-11-28). An invoice made before
        sheet numbers were stored is matched by its start date to the first sheet that day."""
        rows, _ = self.repository.list(company_id, client_id, ["DRAFT", "SENT", "PAID"], 1, 200)
        made: dict[int, InvoiceRow] = {}
        older: list[InvoiceRow] = []
        for row in sorted((row for row in rows if row.source == "SHEET"), key=lambda r: r.number):
            if row.sheet_index is not None:
                made.setdefault(row.sheet_index, row)
            else:
                older.append(row)
        for row in older:
            cycle = next(
                (c for c in cycles if c.index not in made and c.start == row.period_start), None
            )
            if cycle is not None:
                made[cycle.index] = row
        return made

    def _client_cycles(
        self, company_id: UUID, client_id: UUID
    ) -> tuple[list[BudgetCycle], list[Any], list[Any]]:
        """Client payment sheets: each payment received opens a sheet (owner decision
        2026-11-14); delivered videos are taken from it. Work with no payment yet still shows.
        Also returns the payments and deliveries (oldest first) the sheets point into."""
        tz, _, _ = self._zone(company_id)
        payments = self.finance.list_client_payments_for_client(company_id, client_id)
        rows = list(reversed(self.finance.client_deliveries(company_id, client_id, tz)))
        cycles = budget_cycles(
            [
                (
                    payment.received_on,
                    "TOP_UP",
                    Decimal(payment.amount),
                    f"Payment received · {PAYMENT_METHOD_TEXT.get(payment.method, payment.method)}"
                    + (f" · {payment.reference}" if payment.reference else ""),
                    entry_time(payment.received_on, payment.created_at),  # same-day order
                )
                for payment in payments
            ],
            [
                (
                    row.delivered_on,
                    Decimal(row.amount),
                    row.title if row.kind == "PACKAGE" else f"{row.title} · {row.service_name}",
                    row.kind == "WORK",
                    row.delivered_at if row.kind == "WORK" else None,
                )
                for row in rows
            ],
            open_without_payment=True,
        )
        return cycles, payments, rows

    def ensure_sheet_invoices(self, company_id: UUID, client_id: UUID, actor_id: UUID) -> None:
        """A draft invoice for every payment sheet that has finished: its money ran out, or the
        next payment closed it. Made once per sheet; the admin checks and sends it."""
        try:
            cycles, payments, rows = self._client_cycles(company_id, client_id)
            made = self._sheet_invoices(company_id, client_id, cycles)
            for cycle in cycles:
                had_money = cycle.amount + cycle.carried_in > 0
                finished = cycle.end is not None or (had_money and cycle.remaining <= 0)
                if not finished or cycle.items == 0 or cycle.index in made:
                    continue
                invoice_id = self._make_for_sheet(
                    company_id, client_id, actor_id, cycle, payments, rows
                )
                row = self.repository.get(company_id, invoice_id)
                if row is None:
                    continue
                notification_service.notify(
                    company_id,
                    notification_service.admins(company_id),
                    "invoice.ready",
                    f"Invoice {row.code} is ready for {row.client_name}",
                    f"Payment sheet {cycle.index} is complete. Review the draft and send it.",
                    f"/invoices?invoice={row.id}",
                    {"invoice_id": str(row.id), "client_id": str(client_id)},
                )
        except Exception:  # noqa: BLE001 - never block the approval or payment that triggered it
            logger.warning("Automatic sheet invoice failed", exc_info=True)

    def create_for_sheet(
        self, context: AuthContext, request: SheetInvoiceRequest
    ) -> InvoiceDetailResponse:
        """The admin's 'Generate invoice' button on a payment sheet."""
        company_id = self._admin(context, "CREATE")
        if self.tasks.get_client(company_id, request.client_id) is None:
            raise AuthenticationError(404, "CLIENT_NOT_FOUND", "Client was not found.")
        cycles, payments, rows = self._client_cycles(company_id, request.client_id)
        cycle = next(
            (
                item
                for item in cycles
                if item.start == request.start
                and (request.index is None or item.index == request.index)
            ),
            None,
        )
        if cycle is None:
            raise AuthenticationError(404, "SHEET_NOT_FOUND", "That payment sheet was not found.")
        existing = self._sheet_invoices(company_id, request.client_id, cycles).get(cycle.index)
        if existing is not None:
            return self._detail(company_id, existing.id)
        invoice_id = self._make_for_sheet(
            company_id, request.client_id, context.user_id, cycle, payments, rows
        )
        return self._detail(company_id, invoice_id)

    def email_sheet(self, context: AuthContext, request: SheetEmailRequest) -> SheetEmailResponse:
        """The admin's 'Email statement' button. A client gets an email (and a bell notice);
        a manager gets it in their internal mailbox (staff stay inside the app)."""
        overview = self.sheets_overview(context)
        company_id = context.company_id
        assert company_id is not None
        owners = overview.clients if request.kind == "CLIENT" else overview.managers
        owner = next((item for item in owners if item.id == request.owner_id), None)
        sheet = (
            next((item for item in owner.sheets if item.index == request.index), None)
            if owner
            else None
        )
        if owner is None or sheet is None:
            raise AuthenticationError(404, "SHEET_NOT_FOUND", "That payment sheet was not found.")
        currency = overview.currency
        from app.services.finance_service import finance_service
        from app.services.task_events import money_text

        period = (
            f"{sheet.start:%d %b %Y} – {sheet.end:%d %b %Y}"
            if sheet.end
            else f"{sheet.start:%d %b %Y} – now"
        )
        rows = [
            ("Sheet", f"Sheet {sheet.index} · {'closed' if sheet.end else 'open'}"),
            ("Period", period),
            (
                (
                    (
                        f"Extra from sheet {sheet.index - 1}"
                        if Decimal(sheet.carried_in) < 0
                        else f"From sheet {sheet.index - 1}"
                    )
                    if Decimal(sheet.carried_in) != 0
                    else "Carried in"
                ),
                money_text(Decimal(sheet.carried_in), currency),
            ),
            ("Paid in", money_text(Decimal(sheet.paid), currency)),
            (
                "Used",
                f"{money_text(Decimal(sheet.used), currency)} · {sheet.items} {'video' if request.kind == 'CLIENT' else 'task'}{'' if sheet.items == 1 else 's'}",
            ),
            (
                "Extra used" if Decimal(sheet.left) < 0 else "Balance",
                money_text(abs(Decimal(sheet.left)), currency),
            ),
        ]
        from app.services.outbound_mail import app_url, deliver, user_email

        company = self.repository.company_profile(company_id)
        table = finance_service._sheet_table(sheet.lines, currency)
        if request.kind == "MANAGER":
            # Gmail with the statement PDF, plus their internal mailbox (owner request 2026-11-19).
            pdf = render_sheet_statement_pdf(
                company=company,
                owner_label="Manager",
                owner_name=owner.name,
                owner_code=owner.code,
                sheet=sheet,
                currency=currency,
                item_word="task",
            )
            deliver(
                company_id,
                to_email=None,
                user_id=owner.id,
                subject=f"Payment sheet {sheet.index} statement · {owner.name}",
                title=f"Payment sheet {sheet.index}",
                lines=[f"Hello {owner.name}, here is your statement for {period}."],
                rows=rows,
                table=table,
                action_label="Open My Earnings",
                action_url=app_url("MANAGER", "/earnings"),
                company_name=company.name,
                notify_type="sheet.statement",
                notify_link="/earnings",
                attachments=[(pdf, f"{owner.code}-sheet-{sheet.index}.pdf", "application/pdf")],
                mailbox_user=owner.id,
            )
            address = user_email(owner.id)
            return SheetEmailResponse(
                sent_to=owner.name,
                message=(
                    f"Sent to {owner.name}'s mailbox and {address}."
                    if address and not settings.is_internal_email(address)
                    else f"Sent to {owner.name}'s mailbox (no Gmail on file)."
                ),
            )
        email = self.repository.client_login_email(company_id, owner.id)
        if not email:
            raise AuthenticationError(
                422, "NO_CLIENT_EMAIL", "This client has no email address. Add one on their page."
            )
        client_user = notification_service.client_user(company_id, owner.id)
        deliver(
            company_id,
            to_email=email,
            user_id=client_user,
            subject=f"Payment sheet {sheet.index} statement · {owner.name}",
            title=f"Payment sheet {sheet.index}",
            lines=[f"Hello {owner.name}, here is the statement for {period}."],
            rows=rows,
            table=table,
            action_label="Open billing",
            action_url=app_url("CLIENT", "/billing"),
            company_name=company.name,
            notify_type="sheet.statement",
            notify_link="/billing",
            mailbox_user=client_user,
        )
        return SheetEmailResponse(sent_to=email, message=f"Emailed to {email} and their mailbox.")

    def manager_statement_pdf(
        self, context: AuthContext, manager_id: UUID | None, index: int
    ) -> tuple[bytes, str]:
        """A manager's sheet statement PDF: the admin for any manager, a manager for their own."""
        from app.services.finance_service import finance_service

        if manager_id is None:
            earnings = finance_service.my_commission(context)
            company_id = context.company_id
            assert company_id is not None
            me = next(
                (p for p in self.tasks.list_people(company_id) if p.id == context.user_id), None
            )
            sheets = [
                _period_sheet(p) for p in (earnings.wallet.periods if earnings.wallet else [])
            ]
            name, code = (me.name, me.code) if me else ("Manager", "MGR")
            currency = earnings.currency
        else:
            overview = self.sheets_overview(context)
            company_id = context.company_id
            assert company_id is not None
            owner = next((item for item in overview.managers if item.id == manager_id), None)
            if owner is None:
                raise AuthenticationError(404, "SHEET_NOT_FOUND", "That manager was not found.")
            sheets, name, code, currency = owner.sheets, owner.name, owner.code, overview.currency
        sheet = next((item for item in sheets if item.index == index), None)
        if sheet is None:
            raise AuthenticationError(404, "SHEET_NOT_FOUND", "That payment sheet was not found.")
        pdf = render_sheet_statement_pdf(
            company=self.repository.company_profile(company_id),
            owner_label="Manager",
            owner_name=name,
            owner_code=code,
            sheet=sheet,
            currency=currency,
            item_word="task",
        )
        return pdf, f"{code}-sheet-{index}.pdf"

    # -- GST and monthly packages per client (owner requests 2026-11-15) ----------------------

    def _package(self, row: PackageRow, today: date, tz: str) -> PackageResponse:
        status: Literal["UPCOMING", "ACTIVE", "ENDED"] = (
            "UPCOMING"
            if row.starts_on > today
            else "ENDED" if row.ends_on is not None and row.ends_on < today else "ACTIVE"
        )
        month_start = today.replace(day=1)
        month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        return PackageResponse(
            id=row.id,
            name=row.name,
            monthly_price=money(row.monthly_price),
            videos_included=row.videos_included,
            starts_on=row.starts_on,
            ends_on=row.ends_on,
            status=status,
            used_this_month=(
                self.packages.covered_in_month(row.id, tz, month_start, month_end)
                if status == "ACTIVE"
                else 0
            ),
            created_by_name=row.created_by_name,
        )

    def billing_settings(self, context: AuthContext, client_id: UUID) -> BillingSettingsResponse:
        company_id = self._admin(context, "VIEW")
        tax = self.packages.client_tax(company_id, client_id)
        if tax is None:
            raise AuthenticationError(404, "CLIENT_NOT_FOUND", "Client was not found.")
        tz, _, today = self._zone(company_id)
        company = self.repository.company_profile(company_id)
        return BillingSettingsResponse(
            client_id=client_id,
            currency=self.finance.company_currency(company_id),
            gst_enabled=tax.gst_enabled,
            gst_rate=Decimal(tax.gst_rate),
            gstin=tax.gstin,
            company_gstin=company.gstin or "",
            packages=[
                self._package(row, today, tz) for row in self.packages.list(company_id, client_id)
            ],
        )

    def set_gst(
        self, context: AuthContext, client_id: UUID, request: ClientGstRequest
    ) -> BillingSettingsResponse:
        company_id = self._admin(context, "EDIT")
        if not self.packages.set_client_tax(
            company_id, client_id, request.gst_enabled, request.gst_rate, request.gstin.upper()
        ):
            raise AuthenticationError(404, "CLIENT_NOT_FOUND", "Client was not found.")
        return self.billing_settings(context, client_id)

    def add_package(
        self, context: AuthContext, client_id: UUID, request: PackageCreateRequest
    ) -> BillingSettingsResponse:
        """A new monthly package. One package at a time: the running one must end the day
        before (so months already charged keep their price)."""
        company_id = self._admin(context, "CREATE")
        if self.tasks.get_client(company_id, client_id) is None:
            raise AuthenticationError(404, "CLIENT_NOT_FOUND", "Client was not found.")
        running = self.packages.running_after(company_id, client_id, request.starts_on)
        if running is not None:
            raise AuthenticationError(
                409,
                "PACKAGE_RUNNING",
                f"{running.name} is still running then. End it before {request.starts_on:%d %b %Y} first.",
            )
        self.packages.create(
            company_id,
            client_id,
            context.user_id,
            request.name.strip(),
            request.monthly_price,
            request.videos_included,
            request.starts_on,
        )
        return self.billing_settings(context, client_id)

    def end_package(
        self, context: AuthContext, client_id: UUID, package_id: UUID, request: PackageEndRequest
    ) -> BillingSettingsResponse:
        company_id = self._admin(context, "EDIT")
        package = self.packages.get(company_id, package_id)
        if package is None or package.client_id != client_id:
            raise AuthenticationError(404, "PACKAGE_NOT_FOUND", "Package was not found.")
        if not self.packages.end(company_id, package_id, request.ends_on):
            raise AuthenticationError(
                422, "INVALID_END_DATE", "The end date must be on or after the start date."
            )
        return self.billing_settings(context, client_id)

    def remove_package(
        self, context: AuthContext, client_id: UUID, package_id: UUID
    ) -> BillingSettingsResponse:
        company_id = self._admin(context, "DELETE")
        package = self.packages.get(company_id, package_id)
        if package is None or package.client_id != client_id:
            raise AuthenticationError(404, "PACKAGE_NOT_FOUND", "Package was not found.")
        if not self.packages.remove_unstarted(company_id, package_id):
            raise AuthenticationError(
                409,
                "PACKAGE_STARTED",
                "This package has started. End it instead; months already charged stay.",
            )
        return self.billing_settings(context, client_id)

    # -- payment sheets overview (owner request 2026-11-14) -----------------------------------

    @staticmethod
    def _owner(
        kind: Literal["MANAGER", "CLIENT"],
        owner: NamedRef,
        sheets: list[PaymentSheet],
    ) -> SheetOwner:
        current = sheets[-1]
        pot = money(current.carried_in + current.paid)
        left = money(current.left)
        share = float(current.used / pot * 100) if pot > 0 else (100.0 if current.used > 0 else 0)
        status: SheetStatus = (
            "OVER"
            if left < 0
            else (
                "USED_UP"
                if left == 0 and (pot > 0 or current.used > 0)
                else "NEAR" if share >= SHEET_NEAR_PERCENT else "OK"
            )
        )
        return SheetOwner(
            kind=kind,
            id=owner.id,
            name=owner.name,
            code=owner.code,
            status=status,
            left=left,
            pot=pot,
            percent_used=min(share, 100.0),
            ran_out_on=current.ran_out_on,
            sheets=sheets,
        )

    def _client_sheets(
        self, company_id: UUID, client_id: UUID, with_invoices: bool = False
    ) -> list[PaymentSheet]:
        """Client payment sheets (see `_client_cycles`), with each one's invoice when asked."""
        cycles, _, _ = self._client_cycles(company_id, client_id)
        made = self._sheet_invoices(company_id, client_id, cycles) if with_invoices else {}
        return [_sheet(cycle, made.get(cycle.index)) for cycle in cycles]

    def client_budget(self, company_id: UUID, client_id: UUID) -> ClientBudgetSummary:
        """The client's budget is the money they paid (owner model 2026-11-14: each payment opens
        a sheet); used is the work delivered; left is the last sheet's balance."""
        return _budget(self._client_sheets(company_id, client_id))

    def client_sheets(self, context: AuthContext, client_id: UUID) -> list[PaymentSheet]:
        company_id = self._admin(context, "VIEW")
        if self.tasks.get_client(company_id, client_id) is None:
            raise AuthenticationError(404, "CLIENT_NOT_FOUND", "Client not found.")
        return self._client_sheets(company_id, client_id, with_invoices=True)

    def sheets_overview(self, context: AuthContext) -> SheetsOverviewResponse:
        """Every manager's and client's payment sheets, most urgent first (Admin only)."""
        company_id = self._admin(context, "VIEW")
        tz, _, _ = self._zone(company_id)
        clients: list[SheetOwner] = []
        for row in self.finance.client_balances(company_id, tz, None, None):
            sheets = self._client_sheets(company_id, row.client_id, with_invoices=True)
            if sheets:
                clients.append(
                    self._owner(
                        "CLIENT",
                        NamedRef(id=row.client_id, name=row.client_name, code=row.client_code),
                        sheets,
                    )
                )
        managers: list[SheetOwner] = []
        for person in self.tasks.list_people(company_id):
            if person.role != "MANAGER":
                continue
            wallet = finance_service.manager_earnings(company_id, person.id).wallet
            if wallet is None or not wallet.periods:
                continue
            managers.append(
                self._owner(
                    "MANAGER",
                    NamedRef(id=person.id, name=person.name, code=person.code),
                    [_period_sheet(period) for period in wallet.periods],
                )
            )
        urgency = {"OVER": 0, "USED_UP": 1, "NEAR": 2, "OK": 3}

        def order(owner: SheetOwner) -> tuple[int, Decimal, str]:
            return (urgency[owner.status], owner.left, owner.name)

        return SheetsOverviewResponse(
            currency=self.finance.company_currency(company_id),
            managers=sorted(managers, key=order),
            clients=sorted(clients, key=order),
        )

    # -- client portal ----------------------------------------------------------------------

    def client_billing(self, context: AuthContext) -> ClientBillingResponse:
        company_id, client = self._client_of(context)
        tz, zone, today = self._zone(company_id)
        rows_asc = list(reversed(self.finance.client_deliveries(company_id, client.id, tz)))
        deliveries_asc = [(row.delivered_on, Decimal(row.amount)) for row in rows_asc]
        payments = self.finance.list_client_payments_for_client(company_id, client.id)
        # The budget is what the client paid (2026-11-28: the same numbers as the Admin's sheets).
        left = running_budget_left(
            [(payment.received_on, Decimal(payment.amount)) for payment in payments],
            deliveries_asc,
        )
        sheets = self._client_sheets(company_id, client.id)
        totals = self.tasks.budget_totals(company_id, client.id)
        total_paid = money(sum((Decimal(p.amount) for p in payments), ZERO))
        month_start, month_end = resolve_period("this_month", today)
        invoices, _ = self.repository.list(company_id, client.id, ["SENT", "PAID"], 1, 100)
        return ClientBillingResponse(
            client_name=client.name,
            currency=self.finance.company_currency(company_id),
            budget=_budget(sheets),
            total_charged=money(totals.used),
            total_paid=total_paid,
            pending_amount=max(money(totals.used) - total_paid, ZERO),
            current_month_charged=money(
                sum(
                    (
                        Decimal(row.amount)
                        for row in rows_asc
                        if month_start is not None
                        and month_end is not None
                        and month_start <= row.delivered_on <= month_end
                    ),
                    ZERO,
                )
            ),
            cycles=[
                BudgetCycleResponse(
                    index=sheet.index,
                    start=sheet.start,
                    end=sheet.end,
                    amount=sheet.paid,
                    used=sheet.used,
                    remaining=sheet.left,
                    items=sheet.items,
                    carried_in=sheet.carried_in,
                    ran_out_on=sheet.ran_out_on,
                    lines=sheet.lines,
                )
                for sheet in sheets
            ],
            sheets=sheets,
            deliveries=[
                ClientDeliveryRow(
                    delivered_on=row.delivered_on,
                    title=row.title,
                    service_name=row.service_name,
                    amount=money(row.amount),
                    budget_left=balance,
                )
                for row, balance in reversed(list(zip(rows_asc, left, strict=True)))
            ],
            days=[
                ClientDayRow(
                    day=item.day, items=item.items, amount=item.amount, budget_left=item.budget_left
                )
                for item in daily_summary(deliveries_asc, left)
            ],
            payments=[
                ClientPaymentLine(
                    amount=money(payment.amount),
                    received_on=payment.received_on,
                    method=payment.method,
                    reference=payment.reference,
                )
                for payment in payments
            ],
            invoices=[
                ClientInvoiceSummary(
                    id=row.id,
                    code=row.code,
                    status=row.status,
                    period_start=row.period_start,
                    period_end=row.period_end,
                    issue_date=row.issue_date,
                    subtotal=money(row.subtotal),
                    tax_amount=money(row.tax_amount),
                    total=money(row.total),
                    payments_total=money(row.payments_total),
                    balance=_balance(row),
                    items=row.line_count,
                )
                for row in invoices
            ],
        )

    def client_pdf(self, context: AuthContext, invoice_id: UUID) -> tuple[bytes, str]:
        company_id, client = self._client_of(context)
        row = self.repository.get(company_id, invoice_id)
        if row is None or row.client_id != client.id or row.status not in ("SENT", "PAID"):
            raise AuthenticationError(404, "INVOICE_NOT_FOUND", "Invoice was not found.")
        return self._pdf(company_id, invoice_id)


def _portal_url() -> str:
    origins = settings.allowed_origins
    origin = origins[3] if len(origins) > 3 else (origins[0] if origins else "")
    return f"{origin}/billing"


invoice_service = InvoiceService()
