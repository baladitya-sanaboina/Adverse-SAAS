"""Daily reminders (owner decisions 2026-11-15), checked every 15 minutes in the background.

- Tasks due tomorrow, and overdue tasks: a mail in the assignee's internal mailbox, once a day.
- Sent invoices past their due date by 1, 7 and 14 days: an email to the client (with a bell
  notification) and a copy in the admins' internal mailbox. Stops once the invoice is paid.
Nothing is sent before 9 am in the company's own timezone. A Redis lock makes sure only one
backend process runs the check, and Redis keys make sure each reminder goes out once.
"""

from __future__ import annotations

import logging
import threading
from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from app.database.connectivity import database_pool
from app.services import realtime

logger = logging.getLogger(__name__)

CHECK_SECONDS = 15 * 60
SEND_FROM_HOUR = 9
OVERDUE_DAYS = (1, 7, 14)
DAY = 24 * 60 * 60


def _companies() -> list[tuple[UUID, str]]:
    with database_pool.connection(timeout=5) as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT c.id, COALESCE(NULLIF(d.timezone,''), NULLIF(c.timezone,''), 'UTC') "
            "FROM companies c LEFT JOIN company_tenant_defaults d ON d.company_id = c.id "
            "WHERE EXISTS (SELECT 1 FROM tasks t WHERE t.company_id = c.id) "
            "OR EXISTS (SELECT 1 FROM invoices i WHERE i.company_id = c.id)"
        )
        return [(row[0], str(row[1])) for row in cursor.fetchall()]


def _due_tasks(company_id: UUID, today: date) -> list[tuple]:  # type: ignore[type-arg]
    with database_pool.connection(timeout=5) as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT t.id, t.number, t.title, t.due_date, t.assignee_user_id, c.name "
            "FROM tasks t JOIN clients c ON c.id = t.client_id "
            "WHERE t.company_id = %s AND t.assignee_user_id IS NOT NULL AND t.due_date IS NOT NULL "
            "AND t.status IN ('ASSIGNED','IN_PROGRESS') AND t.due_date <= %s",
            (company_id, today + timedelta(days=1)),
        )
        return list(cursor.fetchall())


def _overdue_invoices(company_id: UUID, today: date) -> list[tuple]:  # type: ignore[type-arg]
    with database_pool.connection(timeout=5) as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT i.id, i.prefix, i.number, i.client_id, i.due_date, i.currency, "
            "i.subtotal + i.tax_amount - i.payments_total, c.name "
            "FROM invoices i JOIN clients c ON c.id = i.client_id "
            "WHERE i.company_id = %s AND i.status = 'SENT' AND i.due_date IS NOT NULL "
            "AND i.due_date < %s",
            (company_id, today),
        )
        return list(cursor.fetchall())


def _first(key: str, seconds: int) -> bool:
    return bool(realtime._redis().set(f"reminders:{key}", "1", nx=True, ex=seconds))


def run_once(now: datetime | None = None) -> None:
    from app.services.mail_service import mail_service
    from app.services.notification_service import notification_service
    from app.services.outbound_mail import app_url, deliver
    from app.services.task_events import money_text

    for company_id, tz in _companies():
        try:
            zone = ZoneInfo(tz)
        except Exception:  # noqa: BLE001
            zone = ZoneInfo("UTC")
        local = (now or datetime.now(zone)).astimezone(zone)
        if local.hour < SEND_FROM_HOUR:
            continue
        today = local.date()
        for task_id, number, title, due, assignee, client in _due_tasks(company_id, today):
            late = due < today
            label = "Overdue" if late else "Due tomorrow" if due > today else "Due today"
            if not _first(f"task:{task_id}:{today}", 2 * DAY):
                continue
            mail_service.system(
                company_id,
                [assignee],
                f"{label}: TSK-{number:04d} {title}",
                "\n".join(
                    [
                        f"{'This task was due on' if late else 'This task is due on'} {due:%A %d %b %Y}.",
                        "Submit it for review when it is ready, or tell the admin if it needs more time.",
                        "",
                        f"Task: TSK-{number:04d} · {title}",
                        f"Client: {client}",
                    ]
                ),
                f"/tasks?task={task_id}",
                "REMINDER",
            )
        admins = notification_service.admins(company_id)
        for row in _overdue_invoices(company_id, today):
            invoice_id, prefix, number, client_id, due, currency, balance, client = row
            days = (today - due).days
            if days not in OVERDUE_DAYS or Decimal(balance) <= 0:
                continue
            if not _first(f"invoice:{invoice_id}:{days}", 3 * DAY):
                continue
            code = f"{prefix}-{number:04d}"
            amount = money_text(Decimal(balance), currency)
            from app.repositories.invoice_repository import InvoiceRepository

            invoices = InvoiceRepository()
            deliver(
                company_id,
                to_email=invoices.client_login_email(company_id, client_id),
                user_id=None,
                subject=f"Reminder: invoice {code} is {days} {'day' if days == 1 else 'days'} overdue",
                title=f"Invoice {code} is overdue",
                lines=[
                    f"Hello {client}, invoice {code} was due on {due:%d %b %Y}. "
                    f"{amount} is still to be paid.",
                    "If you have already paid, thank you, please ignore this reminder.",
                ],
                rows=[("Invoice", code), ("Due on", f"{due:%d %b %Y}"), ("Balance due", amount)],
                action_label="View invoice",
                action_url=app_url("CLIENT", "/billing"),
                company_name=invoices.company_profile(company_id).name,
            )
            notification_service.notify(
                company_id,
                [notification_service.client_user(company_id, client_id)],
                "invoice.overdue",
                f"Invoice {code} is overdue",
                f"{amount} was due on {due:%d %b %Y}.",
                "/billing",
                {"invoice_id": str(invoice_id)},
            )
            mail_service.system(
                company_id,
                admins,
                f"Overdue reminder sent: {code} · {client}",
                f"{client} was reminded that {amount} on {code} is {days} days overdue.",
                f"/invoices?invoice={invoice_id}",
                "INVOICE",
            )


def _loop(stop: threading.Event) -> None:
    while not stop.wait(30 if not stop.is_set() else 0):
        try:
            if _first("lock", CHECK_SECONDS - 60):
                run_once()
        except Exception:  # noqa: BLE001 - try again at the next check
            logger.warning("Reminder check failed", exc_info=True)
        stop.wait(CHECK_SECONDS)


_stop = threading.Event()


def start() -> None:
    threading.Thread(target=_loop, args=(_stop,), name="reminders", daemon=True).start()


def stop() -> None:
    _stop.set()
