"""Monthly packages and GST (owner requests 2026-11-15), without a database."""

import unittest
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from app.repositories.package_repository import ClientTaxRow, PackageRow
from app.repositories.task_repository import TaskMutation
from app.services.invoice_service import InvoiceService
from app.services.production_rules import budget_cycles
from app.services.task_service import TaskService
from tests.test_task_service import COMPANY, FakeFinanceRepository, FakeTaskRepository, task_row


class FakePackages:
    def __init__(self, videos: int = 2, used: int = 0, active: bool = True) -> None:
        self.package = PackageRow(
            uuid4(),
            uuid4(),
            "Reels package",
            Decimal("30000"),
            videos,
            date(2026, 11, 1),
            None,
            "Admin",
            datetime(2026, 11, 1),
        )
        self.used = used
        self.active = active
        self.tax = ClientTaxRow(True, Decimal("18"), "29ABCDE1234F1Z5")

    def active_on(self, company_id: UUID, client_id: UUID, day: date) -> PackageRow | None:
        return self.package if self.active else None

    def covered_in_month(self, package_id: UUID, tz: str, start: date, end: date) -> int:
        return self.used

    def client_tax(self, company_id: UUID, client_id: UUID) -> ClientTaxRow:
        return self.tax


class PackageCoverTest(unittest.TestCase):
    def service(self, packages: FakePackages) -> TaskService:
        return TaskService(
            FakeTaskRepository(), FakeFinanceRepository(), packages=packages  # type: ignore[arg-type]
        )

    def test_video_within_the_package_is_covered_at_zero(self) -> None:
        packages = FakePackages(videos=2, used=1)
        mutation = TaskMutation()
        self.service(packages)._cover_by_package(COMPANY, task_row(), mutation)
        self.assertEqual(mutation.updates["client_price_final"], Decimal("0.00"))
        self.assertEqual(mutation.updates["package_id"], packages.package.id)
        self.assertIn("2 of 2", mutation.updates["client_price_reason"])
        field, old, new, _ = mutation.price_changes[0]
        self.assertEqual((field, old, new), ("CLIENT_PRICE", Decimal("400.00"), Decimal("0.00")))

    def test_extra_video_keeps_its_price(self) -> None:
        mutation = TaskMutation()
        self.service(FakePackages(videos=2, used=2))._cover_by_package(
            COMPANY, task_row(), mutation
        )
        self.assertEqual(mutation.updates, {})

    def test_no_package_no_change(self) -> None:
        mutation = TaskMutation()
        self.service(FakePackages(active=False))._cover_by_package(COMPANY, task_row(), mutation)
        self.assertEqual(mutation.updates, {})


class PackageMoneyTest(unittest.TestCase):
    def test_package_charge_is_money_used_but_not_a_video(self) -> None:
        cycles = budget_cycles(
            [(date(2026, 11, 1), "TOP_UP", Decimal("50000"), "Payment")],
            [
                (date(2026, 11, 1), Decimal("30000"), "Reels package · Nov 2026", False),
                (date(2026, 11, 3), Decimal("0"), "Launch reel · Reel", True),
                (date(2026, 11, 4), Decimal("1000"), "Extra reel · Reel", True),
            ],
        )
        self.assertEqual(cycles[0].items, 2)
        self.assertEqual(cycles[0].used, Decimal("31000.00"))
        self.assertEqual(cycles[0].remaining, Decimal("19000.00"))

    def test_gst_is_worked_out_from_the_client_setting(self) -> None:
        service = InvoiceService(packages=FakePackages())  # type: ignore[arg-type]
        rate, amount, gstin = service._tax(COMPANY, uuid4(), Decimal("10000.00"))
        self.assertEqual(
            (rate, amount, gstin), (Decimal("18"), Decimal("1800.00"), "29ABCDE1234F1Z5")
        )
        packages = FakePackages()
        packages.tax = ClientTaxRow(False, Decimal("18"), "")
        off = InvoiceService(packages=packages)  # type: ignore[arg-type]
        self.assertEqual(off._tax(COMPANY, uuid4(), Decimal("10000"))[1], Decimal("0.00"))


if __name__ == "__main__":
    unittest.main()
