"""Invoice PDF (Phase 11): Adverse logo, client details, a table of every video, payments and
the balance. Uses the bundled Poppins font (SIL Open Font License) so the ₹ sign renders."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from typing import Any

from reportlab.lib import colors  # type: ignore[import-untyped]
from reportlab.lib.enums import TA_RIGHT  # type: ignore[import-untyped]
from reportlab.lib.pagesizes import A4  # type: ignore[import-untyped]
from reportlab.lib.styles import ParagraphStyle  # type: ignore[import-untyped]
from reportlab.lib.units import mm  # type: ignore[import-untyped]
from reportlab.pdfbase import pdfmetrics  # type: ignore[import-untyped]
from reportlab.pdfbase.ttfonts import TTFont  # type: ignore[import-untyped]
from reportlab.platypus import (  # type: ignore[import-untyped]
    Image,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.repositories.invoice_repository import CompanyProfile, InvoiceLineRow, InvoiceRow

ASSETS = Path(__file__).resolve().parent.parent / "assets"
BLUE = colors.HexColor("#0876ED")
INK = colors.HexColor("#0F172A")
MUTED = colors.HexColor("#64748B")
LINE = colors.HexColor("#E2E8F0")
TINT = colors.HexColor("#F3F8FF")
GREEN = colors.HexColor("#287150")
RED = colors.HexColor("#B74858")
METHODS = {
    "BANK_TRANSFER": "Bank transfer",
    "UPI": "UPI",
    "CASH": "Cash",
    "CHEQUE": "Cheque",
    "CARD": "Card",
    "OTHER": "Other",
}
SYMBOLS = {"INR": "₹", "USD": "$", "EUR": "€", "GBP": "£"}
_fonts_ready = False


def _fonts() -> None:
    global _fonts_ready
    if _fonts_ready:
        return
    for name, file in (
        ("Poppins", "Poppins-Regular.ttf"),
        ("Poppins-Medium", "Poppins-Medium.ttf"),
        ("Poppins-SemiBold", "Poppins-SemiBold.ttf"),
        ("Poppins-Bold", "Poppins-Bold.ttf"),
    ):
        pdfmetrics.registerFont(TTFont(name, str(ASSETS / "fonts" / file)))
    _fonts_ready = True


def indian_grouping(value: Decimal) -> str:
    """1234567.5 -> '12,34,567.50' (Indian digit grouping)."""
    sign = "-" if value < 0 else ""
    whole, _, fraction = f"{abs(value):.2f}".partition(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups: list[str] = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join([*groups, tail])
    return f"{sign}{whole}.{fraction}"


def amount_text(value: Decimal, currency: str) -> str:
    symbol = SYMBOLS.get(currency, f"{currency} ")
    if currency == "INR":
        text = indian_grouping(Decimal(value))
    else:
        text = f"{Decimal(value):,.2f}"
    return f"-{symbol}{text[1:]}" if text.startswith("-") else f"{symbol}{text}"


def _day(value: date | str | None) -> str:
    if value is None:
        return "—"
    if isinstance(value, str):
        value = date.fromisoformat(value[:10])
    return f"{value:%d %b %Y}"


def _styles() -> dict[str, ParagraphStyle]:
    base = ParagraphStyle("base", fontName="Poppins", fontSize=8.5, leading=12, textColor=INK)
    return {
        "base": base,
        "muted": ParagraphStyle("muted", parent=base, textColor=MUTED, fontSize=8, leading=11),
        "label": ParagraphStyle(
            "label",
            parent=base,
            fontName="Poppins-SemiBold",
            fontSize=7,
            leading=9,
            textColor=MUTED,
        ),
        "strong": ParagraphStyle("strong", parent=base, fontName="Poppins-SemiBold"),
        "title": ParagraphStyle(
            "title",
            parent=base,
            fontName="Poppins-Bold",
            fontSize=22,
            leading=26,
            alignment=TA_RIGHT,
        ),
        "right": ParagraphStyle("right", parent=base, alignment=TA_RIGHT),
        "right_muted": ParagraphStyle(
            "right_muted", parent=base, alignment=TA_RIGHT, textColor=MUTED, fontSize=8
        ),
        "cell": ParagraphStyle("cell", parent=base, fontSize=8, leading=11),
        "head": ParagraphStyle(
            "head",
            parent=base,
            fontName="Poppins-SemiBold",
            fontSize=7.5,
            leading=10,
            textColor=colors.white,
        ),
        "head_right": ParagraphStyle(
            "head_right",
            parent=base,
            fontName="Poppins-SemiBold",
            fontSize=7.5,
            leading=10,
            textColor=colors.white,
            alignment=TA_RIGHT,
        ),
    }


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_invoice_pdf(
    invoice: InvoiceRow, lines: list[InvoiceLineRow], company: CompanyProfile
) -> bytes:
    _fonts()
    s = _styles()
    buffer = BytesIO()
    width = A4[0] - 32 * mm
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=18 * mm,
        title=f"Invoice {invoice.code}",
        author=company.name,
    )
    story: list[Any] = []
    money = invoice.currency

    # Header: logo and title.
    logo = Image(str(ASSETS / "adverse-logo.png"), width=46 * mm, height=46 * mm * 419 / 1600)
    status_color = {"PAID": GREEN, "VOID": RED}.get(invoice.status, BLUE)
    title = Paragraph("INVOICE", s["title"])
    code = Paragraph(
        f'{invoice.code} · <font color="{status_color.hexval().replace("0x", "#")}">'
        f"{invoice.status.title()}</font>",
        s["right_muted"],
    )
    header = Table([[logo, [title, code]]], colWidths=[width * 0.5, width * 0.5])
    header.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    story += [header, Spacer(1, 8 * mm)]

    # From / bill to.
    def block(label: str, name: str, details: list[str | None]) -> list[Any]:
        return [Paragraph(label, s["label"]), Paragraph(_escape(name), s["strong"])] + [
            Paragraph(_escape(item), s["muted"]) for item in details if item
        ]

    parties = Table(
        [
            [
                block(
                    "FROM",
                    company.name,
                    [
                        company.email,
                        company.phone,
                        company.address,
                        f"GSTIN {company.gstin}" if getattr(company, "gstin", None) else None,
                    ],
                ),
                block(
                    "BILL TO",
                    invoice.client_name,
                    [
                        invoice.client_code,
                        invoice.client_email,
                        invoice.client_address or None,
                        f"GSTIN {invoice.client_gstin}" if invoice.client_gstin else None,
                    ],
                ),
            ]
        ],
        colWidths=[width * 0.5, width * 0.5],
    )
    parties.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story += [parties, Spacer(1, 6 * mm)]

    # Key facts strip.
    facts = [
        ("ISSUE DATE", _day(invoice.issue_date)),
        ("WORK PERIOD", f"{_day(invoice.period_start)} – {_day(invoice.period_end)}"),
        ("DUE DATE", _day(invoice.due_date) if invoice.due_date else "On receipt"),
        ("ITEMS", str(len(lines))),
    ]
    strip = Table(
        [[[Paragraph(label, s["label"]), Paragraph(value, s["strong"])] for label, value in facts]],
        colWidths=[width * 0.2, width * 0.42, width * 0.22, width * 0.16],
    )
    strip.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), TINT),
                ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story += [strip, Spacer(1, 7 * mm)]

    # Work table.
    rows: list[list[Any]] = [
        [
            Paragraph("S.No", s["head"]),
            Paragraph("Date", s["head"]),
            Paragraph("Work", s["head"]),
            Paragraph("Service", s["head"]),
            Paragraph("Amount", s["head_right"]),
        ]
    ]
    for line in lines:
        rows.append(
            [
                Paragraph(str(line.position), s["cell"]),
                Paragraph(_day(line.delivered_on), s["cell"]),
                Paragraph(_escape(line.title), s["cell"]),
                Paragraph(_escape(line.service_name), s["cell"]),
                Paragraph(
                    amount_text(line.amount, money),
                    ParagraphStyle("r", parent=s["cell"], alignment=TA_RIGHT),
                ),
            ]
        )
    if not lines:
        rows.append(["", "", Paragraph("No delivered work in this period.", s["muted"]), "", ""])
    table = Table(
        rows,
        colWidths=[width * 0.08, width * 0.16, width * 0.42, width * 0.16, width * 0.18],
        repeatRows=1,
    )
    zebra = [("BACKGROUND", (0, index), (-1, index), TINT) for index in range(2, len(rows), 2)]
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), BLUE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LINEBELOW", (0, 1), (-1, -1), 0.4, LINE),
                *zebra,
            ]
        )
    )
    story += [table, Spacer(1, 6 * mm)]

    # Totals.
    tax = Decimal(invoice.tax_amount)
    balance = Decimal(invoice.subtotal) + tax - Decimal(invoice.payments_total)
    total_rows = [
        ["Work delivered", f"{len(lines)} {'item' if len(lines) == 1 else 'items'}"],
        ["Subtotal", amount_text(invoice.subtotal, money)],
        ["Payments received in this period", amount_text(invoice.payments_total, money)],
    ]
    if tax > 0:
        rate = f"{Decimal(invoice.tax_rate).normalize():f}"
        total_rows.insert(2, [f"GST @ {rate}%", amount_text(tax, money)])
        total_rows.insert(
            3, ["Total with GST", amount_text(Decimal(invoice.subtotal) + tax, money)]
        )
    if Decimal(invoice.budget_added) > 0:
        total_rows.insert(
            2, ["Budget added in this period", amount_text(invoice.budget_added, money)]
        )
    balance_label = "Balance due" if balance > 0 else "Paid in full" if balance == 0 else "Credit"
    total_rows.append([balance_label, amount_text(abs(balance), money)])
    totals = Table(
        [[Paragraph(a, s["muted"]), Paragraph(b, s["right"])] for a, b in total_rows[:-1]]
        + [
            [
                Paragraph(total_rows[-1][0], s["strong"]),
                Paragraph(
                    f'<font name="Poppins-Bold" size="13" color="#0876ED">{total_rows[-1][1]}</font>',
                    s["right"],
                ),
            ]
        ],
        colWidths=[width * 0.36, width * 0.2],
        hAlign="RIGHT",
    )
    totals.setStyle(
        TableStyle(
            [
                ("LINEABOVE", (0, len(total_rows) - 1), (-1, len(total_rows) - 1), 0.8, INK),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, len(total_rows) - 1), (-1, len(total_rows) - 1), 8),
            ]
        )
    )
    story += [KeepTogether([totals]), Spacer(1, 7 * mm)]

    # Payments received.
    if invoice.payments:
        pay_rows: list[list[Any]] = [
            [
                Paragraph("Date", s["label"]),
                Paragraph("Method", s["label"]),
                Paragraph("Reference", s["label"]),
                Paragraph("Amount", ParagraphStyle("lr", parent=s["label"], alignment=TA_RIGHT)),
            ]
        ]
        for payment in invoice.payments:
            pay_rows.append(
                [
                    Paragraph(_day(str(payment.get("received_on"))), s["cell"]),
                    Paragraph(
                        METHODS.get(str(payment.get("method")), str(payment.get("method"))),
                        s["cell"],
                    ),
                    Paragraph(_escape(str(payment.get("reference") or "—")), s["cell"]),
                    Paragraph(
                        amount_text(Decimal(str(payment.get("amount", "0"))), money),
                        ParagraphStyle("pr", parent=s["cell"], alignment=TA_RIGHT),
                    ),
                ]
            )
        payments = Table(
            pay_rows, colWidths=[width * 0.22, width * 0.22, width * 0.34, width * 0.22]
        )
        payments.setStyle(
            TableStyle(
                [
                    ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story += [
            KeepTogether([Paragraph("PAYMENTS RECEIVED", s["label"]), Spacer(1, 2 * mm), payments]),
            Spacer(1, 6 * mm),
        ]

    if invoice.notes:
        story += [Paragraph("NOTES", s["label"]), Paragraph(_escape(invoice.notes), s["muted"])]

    def footer(canvas: Any, document: Any) -> None:
        canvas.saveState()
        canvas.setFont("Poppins", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(
            16 * mm, 10 * mm, f"{company.name} · {invoice.code} · Thank you for your business"
        )
        canvas.drawRightString(A4[0] - 16 * mm, 10 * mm, f"Page {document.page}")
        canvas.setStrokeColor(BLUE)
        canvas.setLineWidth(2)
        canvas.line(0, A4[1] - 2, A4[0], A4[1] - 2)
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()


def render_sheet_statement_pdf(
    *,
    company: CompanyProfile,
    owner_label: str,
    owner_name: str,
    owner_code: str,
    sheet: Any,
    currency: str,
    item_word: str,
) -> bytes:
    """A payment sheet as a statement PDF (owner request 2026-11-19: managers get and can make
    their sheet statement, like a client invoice). `sheet` is a PaymentSheet: carried in + paid
    in, every line with its running balance, and what is left."""
    _fonts()
    s = _styles()
    buffer = BytesIO()
    width = A4[0] - 32 * mm
    number = f"Sheet {sheet.index}"
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=18 * mm,
        title=f"{owner_name} · {number} statement",
        author=company.name,
    )
    story: list[Any] = []
    logo = Image(str(ASSETS / "adverse-logo.png"), width=46 * mm, height=46 * mm * 419 / 1600)
    status = "Closed" if sheet.end else "Open"
    header = Table(
        [
            [
                logo,
                [
                    Paragraph("STATEMENT", s["title"]),
                    Paragraph(f"{number} · {status}", s["right_muted"]),
                ],
            ]
        ],
        colWidths=[width * 0.5, width * 0.5],
    )
    header.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    story += [header, Spacer(1, 8 * mm)]

    def block(label: str, name: str, details: list[str | None]) -> list[Any]:
        return [Paragraph(label, s["label"]), Paragraph(_escape(name), s["strong"])] + [
            Paragraph(_escape(item), s["muted"]) for item in details if item
        ]

    parties = Table(
        [
            [
                block("FROM", company.name, [company.email, company.phone, company.address]),
                block(owner_label.upper(), owner_name, [owner_code]),
            ]
        ],
        colWidths=[width * 0.5, width * 0.5],
    )
    parties.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story += [parties, Spacer(1, 6 * mm)]

    period = f"{_day(sheet.start)} – {_day(sheet.end) if sheet.end else 'now'}"
    facts = [
        ("PERIOD", period),
        ("CARRIED IN", amount_text(Decimal(sheet.carried_in), currency)),
        ("PAID IN", amount_text(Decimal(sheet.paid), currency)),
        (f"{item_word.upper()}S", str(sheet.items)),
    ]
    strip = Table(
        [[[Paragraph(label, s["label"]), Paragraph(value, s["strong"])] for label, value in facts]],
        colWidths=[width * 0.37, width * 0.22, width * 0.22, width * 0.19],
    )
    strip.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), TINT),
                ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story += [strip, Spacer(1, 7 * mm)]

    right = ParagraphStyle("r", parent=s["cell"], alignment=TA_RIGHT)
    rows: list[list[Any]] = [
        [
            Paragraph("Date", s["head"]),
            Paragraph("Details", s["head"]),
            Paragraph("Paid in", s["head_right"]),
            Paragraph("Used", s["head_right"]),
            Paragraph("Balance", s["head_right"]),
        ]
    ]
    for line in sheet.lines:
        amount = Decimal(line.amount)
        rows.append(
            [
                Paragraph(_day(line.day), s["cell"]),
                Paragraph(_escape(line.label), s["cell"]),
                Paragraph(amount_text(amount, currency) if amount > 0 else "", right),
                Paragraph(amount_text(-amount, currency) if amount < 0 else "", right),
                Paragraph(amount_text(Decimal(line.balance), currency), right),
            ]
        )
    if not sheet.lines:
        rows.append(["", Paragraph("Nothing on this sheet yet.", s["muted"]), "", "", ""])
    table = Table(
        rows,
        colWidths=[width * 0.16, width * 0.39, width * 0.15, width * 0.15, width * 0.15],
        repeatRows=1,
    )
    zebra = [("BACKGROUND", (0, index), (-1, index), TINT) for index in range(2, len(rows), 2)]
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), BLUE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LINEBELOW", (0, 1), (-1, -1), 0.4, LINE),
                *zebra,
            ]
        )
    )
    story += [table, Spacer(1, 6 * mm)]

    left = Decimal(sheet.left)
    total_rows = [
        ["Carried in", amount_text(Decimal(sheet.carried_in), currency)],
        ["Paid in", amount_text(Decimal(sheet.paid), currency)],
        [
            f"Used · {sheet.items} {item_word}{'' if sheet.items == 1 else 's'}",
            amount_text(Decimal(sheet.used), currency),
        ],
    ]
    closing = (
        (f"Carried to sheet {sheet.index + 1}" if sheet.end else "Balance now")
        if left >= 0
        else ("Owed, carried to sheet " + str(sheet.index + 1) if sheet.end else "Over by")
    )
    totals = Table(
        [[Paragraph(a, s["muted"]), Paragraph(b, s["right"])] for a, b in total_rows]
        + [
            [
                Paragraph(closing, s["strong"]),
                Paragraph(
                    f'<font name="Poppins-Bold" size="13" color="{"#B74858" if left < 0 else "#0876ED"}">'
                    f"{amount_text(abs(left), currency)}</font>",
                    s["right"],
                ),
            ]
        ],
        colWidths=[width * 0.36, width * 0.2],
        hAlign="RIGHT",
    )
    totals.setStyle(
        TableStyle(
            [
                ("LINEABOVE", (0, len(total_rows)), (-1, len(total_rows)), 0.8, INK),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, len(total_rows)), (-1, len(total_rows)), 8),
            ]
        )
    )
    story += [KeepTogether([totals])]

    def footer(canvas: Any, document: Any) -> None:
        canvas.saveState()
        canvas.setFont("Poppins", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(16 * mm, 10 * mm, f"{company.name} · {owner_name} · {number} statement")
        canvas.drawRightString(A4[0] - 16 * mm, 10 * mm, f"Page {document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
