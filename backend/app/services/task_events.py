"""Turn task changes into notifications (Phase 10).

Called by TaskService after a change has been saved. Every method swallows its own errors so a
notification problem never fails the user's action. Nobody is notified about their own action.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from uuid import UUID

from app.repositories.task_repository import TaskRepository, TaskRow
from app.services.mail_service import MailService, mail_card, mail_service
from app.services.notification_service import NotificationService, notification_service

logger = logging.getLogger(__name__)

STATUS_LABELS = {
    "PENDING": "Pending",
    "ASSIGNED": "Assigned",
    "IN_PROGRESS": "In Progress",
    "SUBMITTED": "Submitted",
    "REVIEW": "Review",
    "APPROVED": "Approved",
    "COMPLETED": "Completed",
    "CANCELLED": "Cancelled",
}
BILLABLE = {"APPROVED", "COMPLETED"}


def _link(row: TaskRow) -> str:
    return f"/tasks?task={row.id}"


def money_text(amount: Decimal, currency: str) -> str:
    symbol = {"INR": "₹", "USD": "$", "EUR": "€", "GBP": "£"}.get(currency, f"{currency} ")
    return f"{symbol}{amount:,.2f}"


def budget_threshold_crossed(
    total: Decimal, used_before: Decimal, used_after: Decimal
) -> str | None:
    """'over' when approved work first uses up the budget (reaches or passes it), 'near' when
    it first reaches 80% without using it up."""
    if total <= 0 or used_after <= used_before:
        return None
    if used_before < total <= used_after:
        return "over"
    near = total * Decimal("0.8")
    if used_before < near <= used_after < total:
        return "near"
    return None


class TaskEvents:
    def __init__(
        self,
        repository: TaskRepository | None = None,
        notifier: NotificationService | None = None,
        mail: MailService | None = None,
    ):
        self.repository = repository or TaskRepository()
        self.notifier = notifier or notification_service
        # Internal mail (owner request 2026-11-15); off when a test passes its own notifier.
        self.mail = mail if mail is not None else (mail_service if notifier is None else None)

    def _mail(
        self,
        company_id: UUID,
        recipients: list[UUID | None],
        subject: str,
        lines: list[str],
        row: TaskRow,
        key: str,
        actor_id: UUID | None = None,
        category: str = "UPDATES",
    ) -> None:
        """Task mails (owner request 2026-11-28): the first mail about a task (you were given it,
        or asked to monitor it) goes to Primary; every later update goes to Updates."""
        if self.mail is None:
            return
        people = [user_id for user_id in recipients if user_id and user_id != actor_id]
        due = f"{row.due_date:%d %b %Y}" if row.due_date else "No date set"
        body = "\n".join(
            [
                *lines,
                "",
                f"Task: {row.code} · {row.title}",
                f"Client: {row.client_name} · {row.service_name}",
                f"Due: {due}",
            ]
        )
        card = mail_card(
            subject,
            lines,
            rows=[
                ("Task", f"{row.code} · {row.title}"),
                ("Client", row.client_name),
                ("Service", row.service_name),
                ("Priority", row.priority.title()),
                ("Due", due),
            ],
            action="Open task",
            status=row.status.replace("_", " ").title(),
        )
        # From the person who acted (owner request 2026-11-19), not from "Adverse".
        self.mail.system(
            company_id,
            people,
            subject,
            body,
            _link(row),
            "TASK",
            once_key=key,
            card=card,
            sender_id=actor_id,
            category=category,
        )

    def _row(self, company_id: UUID, task_id: UUID) -> TaskRow | None:
        try:
            return self.repository.get_task(company_id, task_id)
        except Exception:  # noqa: BLE001
            logger.warning("Could not load task for notification", exc_info=True)
            return None

    def assigned(
        self,
        company_id: UUID,
        task_id: UUID,
        actor_id: UUID,
        previous_assignee: UUID | None,
        previous_monitor: UUID | None,
    ) -> None:
        try:
            row = self._row(company_id, task_id)
            if row is None:
                return
            due = f" · due {row.due_date:%d %b}" if row.due_date else ""
            if row.assignee_user_id and row.assignee_user_id != previous_assignee:
                self.notifier.notify(
                    company_id,
                    [row.assignee_user_id],
                    "task.assigned",
                    f"New task: {row.title}",
                    f"{row.code} · {row.client_name}{due}",
                    _link(row),
                    {"task_id": str(row.id)},
                    exclude=actor_id,
                )
            if row.assignee_user_id and row.assignee_user_id != previous_assignee:
                self._mail(
                    company_id,
                    [row.assignee_user_id],
                    f"New task for you: {row.code} {row.title}",
                    ["You have been given a new task. Open it to see the brief and files."],
                    row,
                    f"task-assigned:{row.id}",
                    actor_id,
                    "PRIMARY",
                )
            if row.monitor_user_id and row.monitor_user_id != previous_monitor:
                self._mail(
                    company_id,
                    [row.monitor_user_id],
                    f"You are monitoring {row.code} {row.title}",
                    [f"Assigned to {row.assignee_name or 'nobody yet'}. You can move its status."],
                    row,
                    f"task-monitor:{row.id}",
                    actor_id,
                    "PRIMARY",
                )
            if row.monitor_user_id and row.monitor_user_id != previous_monitor:
                self.notifier.notify(
                    company_id,
                    [row.monitor_user_id],
                    "task.monitor",
                    f"You are monitoring {row.code}",
                    f"{row.title} · assigned to {row.assignee_name or 'nobody yet'}",
                    _link(row),
                    {"task_id": str(row.id)},
                    exclude=actor_id,
                )
        except Exception:  # noqa: BLE001
            logger.warning("Assignment notification failed", exc_info=True)

    def status_changed(
        self,
        company_id: UUID,
        task_id: UUID,
        actor_id: UUID,
        previous_status: str | None,
        by_admin: bool,
    ) -> None:
        try:
            row = self._row(company_id, task_id)
            if row is None or previous_status == row.status:
                return
            recipients: list[UUID | None] = [row.assignee_user_id, row.monitor_user_id]
            if not by_admin:
                recipients += self.notifier.admins(company_id)
            label = STATUS_LABELS.get(row.status, row.status)
            title = (
                f"{row.code} is ready for review"
                if row.status in {"SUBMITTED", "REVIEW"} and not by_admin
                else f"{row.code} moved to {label}"
            )
            self.notifier.notify(
                company_id,
                recipients,
                "task.status",
                title,
                f"{row.title} · {row.client_name}",
                _link(row),
                {"task_id": str(row.id), "status": row.status, "from": previous_status},
                exclude=actor_id,
            )
            if row.status in {"SUBMITTED", "REVIEW"} and previous_status not in {
                "SUBMITTED",
                "REVIEW",
            }:
                # Work submitted: the admins and the task's manager (owner request 2026-11-15).
                self._mail(
                    company_id,
                    [*self.notifier.admins(company_id), row.monitor_user_id],
                    f"Work submitted: {row.code} {row.title}",
                    [f"{row.assignee_name or 'The assignee'} sent this task for review."],
                    row,
                    f"task-submitted:{row.id}",
                    actor_id,
                )
            elif row.status == "IN_PROGRESS" and previous_status in {"SUBMITTED", "REVIEW"}:
                self._mail(
                    company_id,
                    [row.assignee_user_id],
                    f"Changes requested: {row.code} {row.title}",
                    ["Your work was sent back with changes. Open the task to see the comments."],
                    row,
                    f"task-changes:{row.id}",
                    actor_id,
                )
            if by_admin and row.status in BILLABLE and previous_status not in BILLABLE:
                # Phase 15: the client hears that their video is ready (no price in the alert).
                self.notifier.notify(
                    company_id,
                    [self.notifier.client_user(company_id, row.client_id)],
                    "task.delivered",
                    f"Your video is ready: {row.title}",
                    f"{row.service_name} · it is now on your billing page.",
                    "/billing",
                    {"task_id": str(row.id)},
                    exclude=actor_id,
                )
                self._budget_check(company_id, row, actor_id)
                self._advance_check(company_id, row)
                # Payment sheets (owner request 2026-11-15): a finished sheet gets its draft.
                from app.services.invoice_service import invoice_service

                invoice_service.ensure_sheet_invoices(company_id, row.client_id, actor_id)
        except Exception:  # noqa: BLE001
            logger.warning("Status notification failed", exc_info=True)

    def _budget_check(self, company_id: UUID, row: TaskRow, actor_id: UUID) -> None:
        totals = self.repository.budget_totals(company_id, row.client_id)
        price = Decimal(row.client_price_final or 0)
        crossed = budget_threshold_crossed(totals.total, totals.used - price, totals.used)
        if crossed is None:
            return
        overage = totals.used - totals.total
        left = money_text(totals.total - totals.used, row.currency)
        if crossed == "over":
            used_up = overage == 0
            admin_title = (
                f"{row.client_name} has used their whole budget"
                if used_up
                else f"{row.client_name} is over budget"
            )
            admin_body = (
                "A draft invoice for this top-up is ready to review and send."
                if used_up
                else f"Over by {money_text(overage, row.currency)}. "
                "A draft invoice for this top-up is ready to review and send."
            )
            client_title = "Your budget has been used up"
            client_body = (
                "Please top it up so work continues smoothly."
                if used_up
                else f"Approved work is {money_text(overage, row.currency)} over your budget. "
                "Please contact your agency to top it up."
            )
        else:
            admin_title = f"{row.client_name} has used 80% of their budget"
            admin_body = f"{left} left."
            client_title = "80% of your budget is used"
            client_body = f"{left} left."
        data = {"client_id": str(row.client_id), "level": crossed}
        if self.mail is not None:
            self.mail.system(
                company_id,
                list(self.notifier.admins(company_id)),
                admin_title,
                f"{admin_body}\n\nClient: {row.client_name}",
                f"/clients/{row.client_id}",
                "BUDGET",
                once_key=f"budget-{crossed}:{row.client_id}",
            )
        self.notifier.notify(
            company_id,
            self.notifier.admins(company_id),
            f"budget.{crossed}",
            admin_title,
            admin_body,
            "/invoices" if crossed == "over" else "/payments",
            data,
        )
        self.notifier.notify(
            company_id,
            [self.notifier.client_user(company_id, row.client_id)],
            f"budget.{crossed}",
            client_title,
            client_body,
            "/billing",
            data,
        )

    def _advance_check(self, company_id: UUID, row: TaskRow) -> None:
        """Manager advances (Phase 12): alert when commission first reaches 80% of the money
        advanced, and when it uses the advance up. Work is never blocked."""
        commission = Decimal(row.commission_final or 0)
        if row.assignee_type != "MANAGER" or row.assignee_user_id is None or commission <= 0:
            return
        from app.repositories.finance_repository import FinanceRepository

        finance = FinanceRepository()
        topped = sum(
            (Decimal(p.amount) for p in finance.list_payouts_for(company_id, row.assignee_user_id)),
            Decimal("0"),
        )
        earned = Decimal(finance.manager_earned_totals(company_id).get(row.assignee_user_id, 0))
        crossed = budget_threshold_crossed(topped, earned - commission, earned)
        if crossed is None:
            return
        name = row.assignee_name or "A manager"
        if crossed == "over":
            owed = earned - topped
            admin_title = f"{name}'s advance is used up"
            admin_body = (
                f"Commission is {money_text(owed, row.currency)} more than advanced. Add a top-up."
                if owed > 0
                else "Add a top-up so their next commission is covered."
            )
            own_title = "Your advance is used up"
            own_body = "Your commission keeps counting; the next top-up covers it first."
        else:
            left = money_text(topped - earned, row.currency)
            admin_title = f"{name} has used 80% of their advance"
            admin_body = f"{left} left."
            own_title = "80% of your advance is used"
            own_body = f"{left} left."
        data = {"manager_user_id": str(row.assignee_user_id), "level": crossed}
        if self.mail is not None:
            self.mail.system(
                company_id,
                list(self.notifier.admins(company_id)),
                admin_title,
                f"{admin_body}\n\nManager: {name}",
                "/payments",
                "ADVANCE",
                once_key=f"advance-{crossed}:{row.assignee_user_id}",
            )
        self.notifier.notify(
            company_id,
            self.notifier.admins(company_id),
            f"advance.{crossed}",
            admin_title,
            admin_body,
            "/payments",
            data,
        )
        self.notifier.notify(
            company_id,
            [row.assignee_user_id],
            f"advance.{crossed}",
            own_title,
            own_body,
            "/earnings",
            data,
        )

    def commented(self, company_id: UUID, task_id: UUID, actor_id: UUID, content: str) -> None:
        try:
            row = self._row(company_id, task_id)
            if row is None:
                return
            text = " ".join(content.split())
            self.notifier.notify(
                company_id,
                [row.assignee_user_id, row.monitor_user_id, *self.notifier.admins(company_id)],
                "task.comment",
                f"New comment on {row.code}",
                text[:140] + ("…" if len(text) > 140 else ""),
                _link(row),
                {"task_id": str(row.id)},
                exclude=actor_id,
            )
        except Exception:  # noqa: BLE001
            logger.warning("Comment notification failed", exc_info=True)

    def file_added(
        self, company_id: UUID, task_id: UUID, actor_id: UUID, file_name: str, kind: str
    ) -> None:
        try:
            row = self._row(company_id, task_id)
            if row is None:
                return
            what = "Deliverable uploaded" if kind == "DELIVERABLE" else "Reference file added"
            self.notifier.notify(
                company_id,
                [row.assignee_user_id, row.monitor_user_id, *self.notifier.admins(company_id)],
                "task.file",
                f"{what} on {row.code}",
                file_name,
                _link(row),
                {"task_id": str(row.id)},
                exclude=actor_id,
            )
        except Exception:  # noqa: BLE001
            logger.warning("File notification failed", exc_info=True)


class NoTaskEvents(TaskEvents):
    """Used in unit tests and internal helpers: records nothing, sends nothing."""

    def __init__(self) -> None:  # noqa: D107 - deliberately skips the real dependencies
        pass

    def assigned(self, *args: object, **kwargs: object) -> None:
        return None

    def status_changed(self, *args: object, **kwargs: object) -> None:
        return None

    def commented(self, *args: object, **kwargs: object) -> None:
        return None

    def file_added(self, *args: object, **kwargs: object) -> None:
        return None
