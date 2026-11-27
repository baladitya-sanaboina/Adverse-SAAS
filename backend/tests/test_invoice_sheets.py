"""Owner report 2026-11-28: two payments on the same day made one invoice (same number, old
contents), the invoice said "Credit" and "Amount due" instead of "Budget left", and did not show
the budget left from the sheet before."""

import unittest
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from uuid import uuid4

from pypdf import PdfReader

from app.repositories.invoice_repository import CompanyProfile, InvoiceLineRow, InvoiceRow
from app.services.invoice_pdf import render_invoice_pdf
from app.services.invoice_service import _balance, _balance_line
from app.services.production_rules import budget_cycles

DAY = date(2026, 11, 27)


def invoice(**changes: object) -> InvoiceRow:
    values: dict[str, object] = {
        "id": uuid4(),
        "number": 2,
        "status": "DRAFT",
        "source": "SHEET",
        "client_id": uuid4(),
        "client_name": "Vikas",
        "client_code": "CL-0001",
        "client_email": "vikas@gmail.com",
        "client_address": "",
        "period_start": DAY,
        "period_end": DAY,
        "issue_date": DAY,
        "due_date": None,
        "currency": "INR",
        "subtotal": Decimal("0"),
        "payments_total": Decimal("500"),
        "budget_added": Decimal("0"),
        "payments": [
            {"received_on": "2026-11-27", "method": "UPI", "reference": "", "amount": "500"}
        ],
        "notes": "",
        "created_by_name": "Admin",
        "sent_at": None,
        "paid_at": None,
        "created_at": datetime(2026, 11, 27, 10, 0),
        "line_count": 0,
        "sheet_index": 2,
        "carried_in": Decimal("500"),
    }
    values.update(changes)
    return InvoiceRow(**values)  # type: ignore[arg-type]


class SameDaySheetsTest(unittest.TestCase):
    def test_two_payments_on_one_day_are_two_sheets_with_their_own_items(self) -> None:
        first_paid = datetime(2026, 11, 27, 9, 0)
        work_done = datetime(2026, 11, 27, 11, 0)
        second_paid = datetime(2026, 11, 27, 15, 0)
        first, second = budget_cycles(
            [
                (DAY, "TOP_UP", Decimal("1000"), "Payment received · UPI", first_paid),
                (DAY, "TOP_UP", Decimal("500"), "Payment received · UPI", second_paid),
            ],
            [(DAY, Decimal("500"), "Reel · Editing", True, work_done)],
        )
        self.assertEqual((first.index, first.entry_index, first.delivery_indexes), (1, 0, (0,)))
        self.assertEqual((second.index, second.entry_index, second.delivery_indexes), (2, 1, ()))
        self.assertEqual(first.start, second.start)
        self.assertEqual(second.carried_in, Decimal("500.00"))
        self.assertEqual(second.remaining, Decimal("1000.00"))


class BudgetLeftWordingTest(unittest.TestCase):
    def test_money_left_is_budget_left_not_credit_or_amount_due(self) -> None:
        row = invoice()
        self.assertEqual(_balance(row), Decimal("-1000.00"))
        self.assertEqual(_balance_line(row), ("Budget left", "₹1,000.00"))

    def test_work_over_the_budget_is_an_amount_due(self) -> None:
        row = invoice(subtotal=Decimal("1800"), line_count=1)
        self.assertEqual(_balance_line(row), ("Amount due", "₹800.00"))

    def test_pdf_opens_with_the_previous_budget_left_and_the_payment(self) -> None:
        line = InvoiceLineRow(1, None, DAY, "Reel", "Editing", Decimal("500"))
        pdf = render_invoice_pdf(
            invoice(subtotal=Decimal("500"), line_count=1),
            [line],
            CompanyProfile("Adverse", "old@adverse.in", None, None, None),
        )
        text = " ".join(page.extract_text() or "" for page in PdfReader(BytesIO(pdf)).pages)
        self.assertIn("Previous budget left (from sheet 1)", text)
        self.assertIn("Payment received", text)
        self.assertIn("Budget left", text)
        self.assertNotIn("Credit", text)
        self.assertIn("reachadverse@gmail.com", text)
        self.assertNotIn("old@adverse.in", text)


if __name__ == "__main__":
    unittest.main()
