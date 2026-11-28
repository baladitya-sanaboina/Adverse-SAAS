"""Owner decision 2026-11-28: the Admin dashboard follows the money. Revenue is what clients
paid, team cost is salaries and manager top-ups paid, margin is the difference; work delivered
and commission earned stay as the small print."""

import unittest
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.schemas.production import FinanceSummaryResponse, PeriodQuery, PeriodResponse
from app.services.finance_service import FinanceService

TODAY = date(2026, 11, 28)
PERIOD = PeriodResponse(period="this_month", start=date(2026, 11, 1), end=date(2026, 11, 30))


def summary() -> FinanceSummaryResponse:
    return FinanceSummaryResponse(
        period=PERIOD,
        currency="INR",
        revenue=Decimal("1500"),
        commission_cost=Decimal("300"),
        salary_cost=Decimal("0"),
        team_cost=Decimal("300"),
        gross_margin=Decimal("1200"),
        approved_items=2,
        pending_client_payments=Decimal("0"),
        pending_manager_payments=Decimal("0"),
        pending_salary_payments=Decimal("0"),
        pending_team_payments=Decimal("0"),
        open_tasks=0,
        unassigned_tasks=0,
        in_review_tasks=0,
        overdue_tasks=0,
        top_client=None,
        top_client_open_tasks=0,
    )


class CashDashboardTest(unittest.TestCase):
    def test_revenue_is_money_received_and_team_cost_is_money_paid(self) -> None:
        service = FinanceService.__new__(FinanceService)
        service.repository = MagicMock()
        service.tasks = MagicMock()
        # The owner's real first day: ₹12,000 + ₹1,600 + ₹6,200 in, ₹10,000 top-up out.
        service.repository.cash_in_range.return_value = (
            Decimal("19800"),
            3,
            Decimal("0"),
            Decimal("10000"),
        )
        service.repository.company_currency.return_value = "INR"
        service.repository.attention_tasks.return_value = []
        service.repository.client_balances.return_value = []
        service.repository.status_counts.return_value = {}
        context = MagicMock(company_id=uuid4())
        with (
            patch.object(FinanceService, "_admin", return_value=context.company_id),
            patch.object(FinanceService, "_zone", return_value=("Asia/Kolkata", TODAY)),
            patch.object(
                FinanceService, "_period", return_value=(PERIOD.start, PERIOD.end, PERIOD)
            ),
            patch.object(FinanceService, "_previous_range", return_value=None),
            patch.object(FinanceService, "finance_summary", return_value=summary()),
            patch.object(FinanceService, "team_report", return_value=MagicMock(rows=[])),
        ):
            result = service.admin_dashboard(context, PeriodQuery(period="this_month"))
        money = result.money
        self.assertEqual(money.revenue, Decimal("19800.00"))
        self.assertEqual(money.received_count, 3)
        self.assertEqual(money.team_cost, Decimal("10000.00"))
        self.assertEqual(money.topups_paid, Decimal("10000.00"))
        self.assertEqual(money.gross_margin, Decimal("9800.00"))
        self.assertEqual(money.work_delivered, Decimal("1500.00"))
        self.assertEqual(money.cost_earned, Decimal("300.00"))
        self.assertEqual(result.trend[-1].revenue, Decimal("19800.00"))


if __name__ == "__main__":
    unittest.main()
