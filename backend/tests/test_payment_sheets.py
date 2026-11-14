"""Payment sheet status (owner request 2026-11-14): the Admin sees who needs a top-up."""

import unittest
from datetime import date
from decimal import Decimal
from uuid import uuid4

from app.schemas.invoices import PaymentSheet
from app.schemas.production import NamedRef
from app.services.invoice_service import InvoiceService


def sheet(carried: str, paid: str, used: str) -> PaymentSheet:
    left = Decimal(carried) + Decimal(paid) - Decimal(used)
    return PaymentSheet(
        index=1,
        start=date(2026, 11, 14),
        end=None,
        paid=Decimal(paid),
        carried_in=Decimal(carried),
        used=Decimal(used),
        left=left,
        items=1,
        ran_out_on=None,
        lines=[],
    )


class SheetStatusTest(unittest.TestCase):
    def status(self, carried: str, paid: str, used: str) -> str:
        owner = NamedRef(id=uuid4(), name="Adverse Manager", code="MGR")
        return InvoiceService._owner("MANAGER", owner, [sheet(carried, paid, used)]).status

    def test_statuses(self) -> None:
        self.assertEqual(self.status("0", "10000", "550"), "OK")
        self.assertEqual(self.status("0", "10000", "8000"), "NEAR")  # 80% used
        self.assertEqual(self.status("0", "10000", "10000"), "USED_UP")
        self.assertEqual(self.status("0", "10000", "10500"), "OVER")
        # A carried minus counts against the new payment.
        self.assertEqual(self.status("-2000", "5000", "2500"), "NEAR")

    def test_percent_uses_carried_money(self) -> None:
        owner = NamedRef(id=uuid4(), name="Client", code="CLI")
        result = InvoiceService._owner("CLIENT", owner, [sheet("2000", "8000", "5000")])
        self.assertEqual(
            (result.pot, result.left, result.percent_used),
            (Decimal("10000"), Decimal("5000"), 50.0),
        )


if __name__ == "__main__":
    unittest.main()
