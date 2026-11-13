import unittest
from datetime import date, datetime, timezone
from decimal import Decimal

from app.services.production_rules import (
    SalaryRate,
    allowed_transitions,
    budget_position,
    can_transition,
    is_overdue,
    resolve_period,
    salary_cost_in_range,
    salary_due_by_month,
    status_timestamp_updates,
    task_margin,
)

NOW = datetime(2026, 11, 13, 10, 0, tzinfo=timezone.utc)


class StatusRulesTest(unittest.TestCase):
    def test_only_admin_can_approve_complete_or_cancel(self) -> None:
        for role in ("ASSIGNEE", "MONITOR"):
            for current in ("ASSIGNED", "IN_PROGRESS", "SUBMITTED", "REVIEW"):
                for target in ("APPROVED", "COMPLETED", "CANCELLED"):
                    self.assertFalse(
                        can_transition(role, current, target, True), (role, current, target)
                    )
        self.assertTrue(can_transition("ADMIN", "REVIEW", "APPROVED", True))
        self.assertTrue(can_transition("ADMIN", "SUBMITTED", "COMPLETED", True))

    def test_assignee_moves_own_work_up_to_submitted(self) -> None:
        self.assertEqual(allowed_transitions("ASSIGNEE", "ASSIGNED", True), ["IN_PROGRESS"])
        self.assertEqual(allowed_transitions("ASSIGNEE", "IN_PROGRESS", True), ["SUBMITTED"])
        self.assertEqual(allowed_transitions("ASSIGNEE", "SUBMITTED", True), ["IN_PROGRESS"])
        self.assertEqual(allowed_transitions("ASSIGNEE", "REVIEW", True), [])
        self.assertFalse(can_transition("ASSIGNEE", "SUBMITTED", "REVIEW", True))

    def test_monitor_can_move_to_review_and_request_changes(self) -> None:
        self.assertIn("REVIEW", allowed_transitions("MONITOR", "SUBMITTED", True))
        self.assertEqual(allowed_transitions("MONITOR", "REVIEW", True), ["IN_PROGRESS"])
        self.assertEqual(allowed_transitions("MONITOR", "APPROVED", True), [])

    def test_admin_needs_an_assignee_to_move_work_forward(self) -> None:
        options = allowed_transitions("ADMIN", "PENDING", False)
        self.assertEqual(options, ["CANCELLED"])
        self.assertNotIn("PENDING", allowed_transitions("ADMIN", "ASSIGNED", True))

    def test_approval_sets_and_reopening_clears_billable_timestamps(self) -> None:
        approved = status_timestamp_updates(
            "APPROVED", NOW, assigned_at=NOW, started_at=NOW, approved_at=None
        )
        self.assertEqual(approved["approved_at"], NOW)
        self.assertIsNone(approved["completed_at"])
        completed = status_timestamp_updates(
            "COMPLETED", NOW, assigned_at=NOW, started_at=NOW, approved_at=datetime(2026, 11, 1)
        )
        self.assertEqual(completed["approved_at"], datetime(2026, 11, 1))  # keeps first approval
        self.assertEqual(completed["completed_at"], NOW)
        reopened = status_timestamp_updates(
            "IN_PROGRESS", NOW, assigned_at=NOW, started_at=NOW, approved_at=NOW
        )
        self.assertIsNone(reopened["approved_at"])  # no longer billable
        self.assertNotIn("started_at", reopened)  # first start time is kept
        cancelled = status_timestamp_updates(
            "CANCELLED", NOW, assigned_at=NOW, started_at=NOW, approved_at=NOW
        )
        self.assertIsNone(cancelled["approved_at"])
        self.assertEqual(cancelled["cancelled_at"], NOW)

    def test_overdue_only_for_open_tasks(self) -> None:
        today = date(2026, 11, 13)
        self.assertTrue(is_overdue("IN_PROGRESS", date(2026, 11, 12), today))
        self.assertFalse(is_overdue("APPROVED", date(2026, 11, 12), today))
        self.assertFalse(is_overdue("IN_PROGRESS", date(2026, 11, 13), today))
        self.assertFalse(is_overdue("IN_PROGRESS", None, today))


class MoneyRulesTest(unittest.TestCase):
    def test_margin_for_manager_and_salaried_employee(self) -> None:
        self.assertEqual(task_margin(Decimal("400"), Decimal("300")), Decimal("100.00"))
        self.assertEqual(task_margin(Decimal("900"), Decimal("500")), Decimal("400.00"))
        self.assertEqual(task_margin(Decimal("400"), None), Decimal("400.00"))

    def test_owner_example_budget_exceeded_after_twelve_videos(self) -> None:
        # Budget 12,000 at 1,000 per video: 12 approved videos use it exactly; the 13th exceeds.
        at_limit = budget_position(Decimal("12000"), Decimal("12000"), Decimal("0"))
        self.assertEqual(at_limit.remaining, Decimal("0.00"))
        self.assertEqual(at_limit.overage, Decimal("0.00"))
        next_video = budget_position(
            Decimal("12000"), Decimal("12000"), Decimal("0"), Decimal("1000")
        )
        self.assertTrue(next_video.exceeds_with_new_task)
        self.assertEqual(next_video.projected_overage, Decimal("1000.00"))

    def test_budget_counts_committed_work_in_the_warning(self) -> None:
        position = budget_position(
            Decimal("12000"), Decimal("8000"), Decimal("3000"), Decimal("1000")
        )
        self.assertFalse(position.exceeds_with_new_task)  # 8000 + 3000 + 1000 = 12000
        self.assertEqual(position.remaining, Decimal("4000.00"))
        over = budget_position(Decimal("12000"), Decimal("8000"), Decimal("3500"), Decimal("1000"))
        self.assertTrue(over.exceeds_with_new_task)
        self.assertEqual(over.projected_overage, Decimal("500.00"))

    def test_no_budget_never_warns(self) -> None:
        position = budget_position(Decimal("0"), Decimal("5000"), Decimal("0"), Decimal("1000"))
        self.assertFalse(position.has_budget)
        self.assertFalse(position.exceeds_with_new_task)
        self.assertEqual(position.overage, Decimal("0.00"))


class PeriodTest(unittest.TestCase):
    def test_presets(self) -> None:
        today = date(2026, 11, 13)  # a Friday
        self.assertEqual(resolve_period("all", today), (None, None))
        self.assertEqual(resolve_period("today", today), (today, today))
        self.assertEqual(
            resolve_period("this_week", today), (date(2026, 11, 9), date(2026, 11, 15))
        )
        self.assertEqual(
            resolve_period("this_month", today), (date(2026, 11, 1), date(2026, 11, 30))
        )
        self.assertEqual(
            resolve_period("previous_month", today), (date(2026, 10, 1), date(2026, 10, 31))
        )
        self.assertEqual(
            resolve_period("previous_month", date(2026, 1, 5)),
            (date(2025, 12, 1), date(2025, 12, 31)),
        )

    def test_custom_range_validation(self) -> None:
        today = date(2026, 11, 13)
        self.assertEqual(
            resolve_period("custom", today, date(2026, 1, 1), date(2026, 3, 31)),
            (date(2026, 1, 1), date(2026, 3, 31)),
        )
        with self.assertRaises(ValueError):
            resolve_period("custom", today, date(2026, 3, 1), date(2026, 1, 1))
        with self.assertRaises(ValueError):
            resolve_period("custom", today, None, date(2026, 1, 1))


class SalaryTest(unittest.TestCase):
    def test_monthly_salary_due_with_a_raise(self) -> None:
        rates = [
            SalaryRate(Decimal("25000"), date(2026, 9, 1), date(2026, 11, 1)),
            SalaryRate(Decimal("30000"), date(2026, 11, 1), None),
        ]
        due = salary_due_by_month(rates, date(2026, 11, 13))
        self.assertEqual(
            due,
            [
                (date(2026, 9, 1), Decimal("25000.00")),
                (date(2026, 10, 1), Decimal("25000.00")),
                (date(2026, 11, 1), Decimal("30000.00")),
            ],
        )

    def test_salary_stops_after_it_ends(self) -> None:
        rates = [SalaryRate(Decimal("20000"), date(2026, 8, 1), date(2026, 10, 1))]
        due = salary_due_by_month(rates, date(2026, 11, 13))
        self.assertEqual([month for month, _ in due], [date(2026, 8, 1), date(2026, 9, 1)])

    def test_salary_cost_is_prorated_for_short_ranges(self) -> None:
        rates = [SalaryRate(Decimal("30000"), date(2026, 1, 1), None)]
        self.assertEqual(
            salary_cost_in_range(rates, date(2026, 11, 1), date(2026, 11, 30)), Decimal("30000.00")
        )
        self.assertEqual(
            salary_cost_in_range(rates, date(2026, 11, 13), date(2026, 11, 13)), Decimal("1000.00")
        )
        self.assertEqual(salary_due_by_month([], date(2026, 11, 13)), [])


if __name__ == "__main__":
    unittest.main()
