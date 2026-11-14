"""Notifications (Phase 10): threshold rule and delivery rules, without a database or Redis."""

import unittest
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

from app.services.notification_service import NotificationService
from app.services.task_events import budget_threshold_crossed


class BudgetThresholdTest(unittest.TestCase):
    def test_first_time_over_budget(self) -> None:
        self.assertEqual(
            budget_threshold_crossed(Decimal("10000"), Decimal("9500"), Decimal("10500")), "over"
        )

    def test_reaching_eighty_percent(self) -> None:
        self.assertEqual(
            budget_threshold_crossed(Decimal("10000"), Decimal("7000"), Decimal("8000")), "near"
        )

    def test_no_repeat_once_past_a_level(self) -> None:
        self.assertIsNone(
            budget_threshold_crossed(Decimal("10000"), Decimal("8500"), Decimal("9000"))
        )
        self.assertIsNone(
            budget_threshold_crossed(Decimal("10000"), Decimal("11000"), Decimal("12000"))
        )

    def test_no_budget_or_no_increase(self) -> None:
        self.assertIsNone(budget_threshold_crossed(Decimal("0"), Decimal("0"), Decimal("500")))
        self.assertIsNone(budget_threshold_crossed(Decimal("1000"), Decimal("900"), Decimal("900")))

    def test_exactly_used_up_counts_as_over(self) -> None:
        self.assertEqual(
            budget_threshold_crossed(Decimal("1000"), Decimal("900"), Decimal("1000")), "over"
        )

    def test_jump_straight_over_reports_over(self) -> None:
        self.assertEqual(
            budget_threshold_crossed(Decimal("1000"), Decimal("100"), Decimal("1500")), "over"
        )


class FakeNotificationRepository:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[list[object]] = []

    def insert_many(self, company_id, user_ids, type_, title, body, link, data):  # type: ignore[no-untyped-def]
        if self.fail:
            raise RuntimeError("database down")
        self.calls.append(list(user_ids))
        return {}


class NotifyRulesTest(unittest.TestCase):
    def test_dedupes_and_skips_actor_and_empty(self) -> None:
        repo = FakeNotificationRepository()
        service = NotificationService(repo)  # type: ignore[arg-type]
        actor, other = uuid4(), uuid4()
        with patch("app.services.notification_service.realtime.publish"):
            service.notify(uuid4(), [actor, other, other, None], "t", "Title", exclude=actor)
        self.assertEqual(repo.calls, [[other]])

    def test_nothing_to_send_skips_storage(self) -> None:
        repo = FakeNotificationRepository()
        service = NotificationService(repo)  # type: ignore[arg-type]
        actor = uuid4()
        service.notify(uuid4(), [actor, None], "t", "Title", exclude=actor)
        self.assertEqual(repo.calls, [])

    def test_storage_failure_never_raises(self) -> None:
        service = NotificationService(FakeNotificationRepository(fail=True))  # type: ignore[arg-type]
        service.notify(uuid4(), [uuid4()], "t", "Title")


if __name__ == "__main__":
    unittest.main()


class DeliveredNotificationTest(unittest.TestCase):
    """Phase 15: when the admin approves a video the client is told it is ready (no price)."""

    def _row(self, status: str):  # type: ignore[no-untyped-def]
        from datetime import datetime, timezone

        from app.repositories.task_repository import TaskRow

        now = datetime(2026, 11, 14, tzinfo=timezone.utc)
        return TaskRow(
            id=uuid4(),
            number=9,
            title="Diwali reel",
            description="",
            priority="HIGH",
            status=status,
            client_id=uuid4(),
            client_name="Client",
            client_code="C",
            service_id=uuid4(),
            service_name="Reel",
            service_code="REEL",
            assignee_user_id=uuid4(),
            assignee_name="E",
            assignee_type="EMPLOYEE",
            monitor_user_id=None,
            monitor_name=None,
            due_date=None,
            currency="INR",
            client_pricing_model="PER_VIDEO",
            client_price_default=Decimal("800"),
            client_price_final=Decimal("800"),
            client_price_reason="",
            commission_default=None,
            commission_final=None,
            commission_reason="",
            created_by_name="Admin",
            created_at=now,
            updated_at=now,
            assigned_at=now,
            started_at=now,
            submitted_at=now,
            approved_at=now,
            completed_at=None,
            cancelled_at=None,
        )

    def test_client_hears_about_an_approved_video(self) -> None:
        from types import SimpleNamespace
        from unittest.mock import MagicMock

        from app.services.task_events import TaskEvents

        client_login = uuid4()
        repository = MagicMock()
        repository.get_task.return_value = self._row("APPROVED")
        repository.budget_totals.return_value = SimpleNamespace(
            total=Decimal("0"), used=Decimal("800"), committed=Decimal("0")
        )
        notifier = MagicMock()
        notifier.client_user.return_value = client_login
        TaskEvents(repository, notifier).status_changed(
            uuid4(), uuid4(), uuid4(), "SUBMITTED", by_admin=True
        )
        delivered = [c for c in notifier.notify.call_args_list if c.args[2] == "task.delivered"]
        self.assertEqual(len(delivered), 1)
        self.assertEqual(delivered[0].args[1], [client_login])
        self.assertNotIn("800", delivered[0].args[3] + delivered[0].args[4])

    def test_no_client_alert_for_work_in_progress(self) -> None:
        from unittest.mock import MagicMock

        from app.services.task_events import TaskEvents

        repository = MagicMock()
        repository.get_task.return_value = self._row("SUBMITTED")
        notifier = MagicMock()
        TaskEvents(repository, notifier).status_changed(
            uuid4(), uuid4(), uuid4(), "IN_PROGRESS", by_admin=False
        )
        self.assertFalse(any(c.args[2] == "task.delivered" for c in notifier.notify.call_args_list))
