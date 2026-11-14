"""Client invoices and the client billing view (Phase 11).

An invoice is a snapshot of the work a client received in a period (usually one budget top-up)
plus the payments received in that period. No tax for now (owner decision 2026-11-14).
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from app.core.settings import settings
from app.repositories.finance_repository import FinanceRepository
from app.repositories.invoice_repository import InvoiceRepository, InvoiceRow
from app.repositories.task_repository import TaskRepository
from app.schemas.authentication import AuthContext
from app.schemas.invoices import (
    BudgetCycleResponse,
    ClientBillingResponse,
    ClientDayRow,
    ClientDeliveryRow,
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
    PaymentSheet,
    SheetOwner,
    SheetsOverviewResponse,
    SheetStatus,
)
from app.schemas.production import ClientBudgetSummary, ClientPaymentLine, NamedRef, SheetLine
from app.services.authentication_service import AuthenticationError
from app.services.finance_service import finance_service
from app.services.invoice_pdf import amount_text, render_invoice_pdf
from app.services.notification_service import notification_service
from app.services.permission_service import validate_user_action_access
from app.services.production_rules import (
    budget_cycles,
    budget_position,
    daily_summary,
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


class InvoiceService:
    def __init__(
        self,
        repository: InvoiceRepository | None = None,
        finance: FinanceRepository | None = None,
        tasks: TaskRepository | None = None,
    ):
        self.repository = repository or InvoiceRepository()
        self.finance = finance or FinanceRepository()
        self.tasks = tasks or TaskRepository()

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
                (row.delivered_on, Decimal(row.amount), f"{row.title} · {row.service_name}")
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
            payments_total=money(row.payments_total),
            budget_added=money(row.budget_added),
            balance=money(Decimal(row.subtotal) - Decimal(row.payments_total)),
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
        _, _, today = self._zone(company_id)
        deliveries, payments, budget_added = self._collect(company_id, client_id, start, end)
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
                "subtotal": money(sum((Decimal(row.amount) for row in deliveries), ZERO)),
                "payments_total": money(sum((Decimal(p.amount) for p in payments), ZERO)),
                "budget_added": money(budget_added),
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
        return InvoicePreviewResponse(
            period_start=start,
            period_end=end,
            currency=self.finance.company_currency(company_id),
            items=len(deliveries),
            subtotal=subtotal,
            payments_total=paid,
            budget_added=money(budget_added),
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
                    amount=amount_text(Decimal(row.subtotal), row.currency),
                    period=f"{row.period_start:%d %b %Y} – {row.period_end:%d %b %Y}",
                    portal_url=_portal_url(),
                    pdf=content,
                    filename=filename,
                )
                emailed, message = True, f"Emailed to {email}."
            except Exception:  # noqa: BLE001 - the invoice is still available in the portal
                logger.warning("Invoice email failed", exc_info=True)
                message = "The email could not be sent; the invoice is in the client portal."
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
            f"{amount_text(Decimal(row.subtotal), row.currency)} for "
            f"{row.period_start:%d %b} – {row.period_end:%d %b %Y}.",
            "/billing",
            {"invoice_id": str(row.id)},
        )
        return InvoiceSendResponse(
            invoice=self._detail(company_id, invoice_id), emailed=emailed, message=message
        )

    def create_for_used_up_budget(self, company_id: UUID, client_id: UUID, actor_id: UUID) -> None:
        """Called when approved work uses up a client's budget: prepare a draft for the current
        top-up period (once per period) and tell the admins."""
        try:
            cycles, _ = self._cycles(company_id, client_id)
            if not cycles:
                return
            current = cycles[-1]
            if current.invoice_id is not None or self.repository.find_auto(
                company_id, client_id, current.start
            ):
                return
            _, _, today = self._zone(company_id)
            invoice_id = self._make(company_id, client_id, actor_id, current.start, today, "TOP_UP")
            row = self.repository.get(company_id, invoice_id)
            if row is None:
                return
            notification_service.notify(
                company_id,
                notification_service.admins(company_id),
                "invoice.ready",
                f"Invoice {row.code} is ready for {row.client_name}",
                "Their budget is used up. Review the draft and send it.",
                f"/invoices?invoice={row.id}",
                {"invoice_id": str(row.id), "client_id": str(client_id)},
            )
        except Exception:  # noqa: BLE001 - never block the approval that triggered this
            logger.warning("Automatic invoice failed", exc_info=True)

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

    def sheets_overview(self, context: AuthContext) -> SheetsOverviewResponse:
        """Every manager's and client's payment sheets, most urgent first (Admin only)."""
        company_id = self._admin(context, "VIEW")
        tz, _, _ = self._zone(company_id)
        clients: list[SheetOwner] = []
        for row in self.finance.client_balances(company_id, tz, None, None):
            cycles, _ = self._cycles(company_id, row.client_id)
            if cycles:
                clients.append(
                    self._owner(
                        "CLIENT",
                        NamedRef(id=row.client_id, name=row.client_name, code=row.client_code),
                        [
                            PaymentSheet(
                                index=cycle.index,
                                start=cycle.start,
                                end=cycle.end,
                                paid=cycle.amount,
                                carried_in=cycle.carried_in,
                                used=cycle.used,
                                left=cycle.remaining,
                                items=cycle.items,
                                ran_out_on=cycle.ran_out_on,
                                lines=cycle.lines,
                            )
                            for cycle in cycles
                        ],
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
                    [
                        PaymentSheet(
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
                        for period in wallet.periods
                    ],
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
        cycles, deliveries_asc = self._cycles(company_id, client.id)
        rows_asc = list(reversed(self.finance.client_deliveries(company_id, client.id, tz)))
        entries = self._budget_entries(company_id, client.id, zone)
        left = running_budget_left([(day, amount) for day, _, amount in entries], deliveries_asc)
        totals = self.tasks.budget_totals(company_id, client.id)
        position = budget_position(totals.total, totals.used, totals.committed)
        payments = self.finance.list_client_payments_for_client(company_id, client.id)
        total_paid = money(sum((Decimal(p.amount) for p in payments), ZERO))
        month_start, month_end = resolve_period("this_month", today)
        invoices, _ = self.repository.list(company_id, client.id, ["SENT", "PAID"], 1, 100)
        return ClientBillingResponse(
            client_name=client.name,
            currency=self.finance.company_currency(company_id),
            budget=ClientBudgetSummary(
                has_budget=position.has_budget,
                total=position.total,
                used=position.used,
                remaining=position.remaining,
                overage=position.overage,
            ),
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
            cycles=cycles,
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
                    payments_total=money(row.payments_total),
                    balance=money(Decimal(row.subtotal) - Decimal(row.payments_total)),
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
