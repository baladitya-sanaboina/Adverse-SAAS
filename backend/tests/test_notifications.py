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
