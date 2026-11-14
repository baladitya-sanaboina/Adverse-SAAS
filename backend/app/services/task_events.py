"""Turn task changes into notifications (Phase 10).

Called by TaskService after a change has been saved. Every method swallows its own errors so a
notification problem never fails the user's action. Nobody is notified about their own action.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from uuid import UUID

from app.repositories.task_repository import TaskRepository, TaskRow
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
    """'over' when approved work first goes past the budget, 'near' when it first reaches 80%."""
    if total <= 0 or used_after <= used_before:
        return None
    if used_before <= total < used_after:
        return "over"
    near = total * Decimal("0.8")
    if used_before < near <= used_after <= total:
        return "near"
    return None


class TaskEvents:
    def __init__(
        self,
        repository: TaskRepository | None = None,
        notifier: NotificationService | None = None,
    ):
        self.repository = repository or TaskRepository()
        self.notifier = notifier or notification_service

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
            if by_admin and row.status in BILLABLE and previous_status not in BILLABLE:
                self._budget_check(company_id, row)
        except Exception:  # noqa: BLE001
            logger.warning("Status notification failed", exc_info=True)

    def _budget_check(self, company_id: UUID, row: TaskRow) -> None:
        totals = self.repository.budget_totals(company_id, row.client_id)
        price = Decimal(row.client_price_final or 0)
        crossed = budget_threshold_crossed(totals.total, totals.used - price, totals.used)
        if crossed is None:
            return
        overage = totals.used - totals.total
        if crossed == "over":
            admin_title = f"{row.client_name} is over budget"
            admin_body = (
                f"Over by {money_text(overage, row.currency)}. Add a top-up or send an invoice."
            )
            client_title = "Your budget has been used up"
            client_body = (
                f"Approved work is {money_text(overage, row.currency)} over your budget. "
                "Please contact your agency to top it up."
            )
        else:
            admin_title = f"{row.client_name} has used 80% of their budget"
            admin_body = f"{money_text(totals.total - totals.used, row.currency)} left."
            client_title = "80% of your budget is used"
            client_body = f"{money_text(totals.total - totals.used, row.currency)} left."
        data = {"client_id": str(row.client_id), "level": crossed}
        self.notifier.notify(
            company_id,
            self.notifier.admins(company_id),
            f"budget.{crossed}",
            admin_title,
            admin_body,
            "/payments",
            data,
        )
        client_user = self.notifier.client_user(company_id, row.client_id)
        self.notifier.notify(
            company_id,
            [client_user],
            f"budget.{crossed}",
            client_title,
            client_body,
            "/dashboard#client-budget-panel",
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
