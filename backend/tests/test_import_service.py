"""Spreadsheet import (owner request 2026-11-19), with .xlsx files built in memory."""

import io
import unittest
import zipfile
from datetime import date
from decimal import Decimal
from typing import Any
from unittest.mock import patch
from uuid import uuid4
from xml.sax.saxutils import escape

from app.repositories.task_repository import ClientRef
from app.services.authentication_service import AuthenticationError
from app.services.import_service import ImportService, parse
from app.services.xlsx_reader import Cell, as_date, is_ticked, read_workbook
from tests.test_task_service import context

CALENDAR: list[list[Any]] = [
    [
        "Date",
        "",
        "Day",
        "Video Topic",
        "Reference Video",
        "Recorded",
        "Script",
        "Edited",
        "Insta-Posted",
        "Youtube-Post",
        "Script",
        "PDF's LINKS",
    ],
    [
        46268,
        "Week-1",
        "Thursday",
        "Keyboard Shortcuts",
        "Link",
        True,
        False,
        True,
        None,
        None,
        "Window keys",
        None,
    ],
    [46270, "Week-1", "Saturday", "No Reel", None, None, None, None, None, None, None, None],
    [None, "Week-2", "Tuesday", "Planned reel", None, None, None, None, None, None, None, None],
    [None, None, None, "An idea without a date", None, None, None, None, None, None, None, None],
]
LINKS = {
    ("Short Form", "E2"): "https://www.instagram.com/reel/abc/",
    ("Short Form", "K2"): "https://docs.google.com/document/d/xyz/edit",
}
DASHBOARD: list[list[Any]] = [
    ["Client Name", "Client Budget", "Selected Date"],
    ["Vikas", "₹22,000", "01-Oct-26"],
    ["Date", "Videos", "Amount", "Budget Left"],
    ["02-Nov-26", 1, 700, 0],
]
TIMESHEET: list[list[Any]] = [
    ["Date", "Work", "Videos", "Rate"],
    ["01-Oct-26", "Slice Promotion", 2, 700],
    ["03-Oct-26", "Carousel", 1, "Rs 700"],
    ["", "", "", ""],
]


def _column(index: int) -> str:
    name = ""
    index += 1
    while index:
        index, rest = divmod(index - 1, 26)
        name = chr(65 + rest) + name
    return name


def make_xlsx(sheets: dict[str, list[list[Any]]], links: dict[tuple[str, str], str]) -> bytes:
    strings: list[str] = []

    def shared(text: str) -> int:
        if text not in strings:
            strings.append(text)
        return strings.index(text)

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        entries, rels = [], []
        for number, (name, rows) in enumerate(sheets.items(), start=1):
            entries.append(f'<sheet name="{escape(name)}" sheetId="{number}" r:id="rId{number}"/>')
            rels.append(
                f'<Relationship Id="rId{number}" Type="worksheet" Target="worksheets/sheet{number}.xml"/>'
            )
            body = []
            for r, row in enumerate(rows, start=1):
                cells = []
                for c, value in enumerate(row):
                    ref = f"{_column(c)}{r}"
                    if value is None or value == "":
                        continue
                    if isinstance(value, bool):
                        cells.append(f'<c r="{ref}" t="b"><v>{int(value)}</v></c>')
                    elif isinstance(value, (int, float)):
                        cells.append(f'<c r="{ref}"><v>{value}</v></c>')
                    else:
                        cells.append(f'<c r="{ref}" t="s"><v>{shared(str(value))}</v></c>')
                body.append(f'<row r="{r}">{"".join(cells)}</row>')
            sheet_links = [(ref, url) for (sheet, ref), url in links.items() if sheet == name]
            link_xml = "".join(
                f'<hyperlink ref="{ref}" r:id="rL{i}"/>' for i, (ref, _) in enumerate(sheet_links)
            )
            archive.writestr(
                f"xl/worksheets/sheet{number}.xml",
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                f'<sheetData>{"".join(body)}</sheetData>'
                + (f"<hyperlinks>{link_xml}</hyperlinks>" if link_xml else "")
                + "</worksheet>",
            )
            if sheet_links:
                archive.writestr(
                    f"xl/worksheets/_rels/sheet{number}.xml.rels",
                    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                    + "".join(
                        f'<Relationship Id="rL{i}" Type="hyperlink" Target="{escape(url)}" TargetMode="External"/>'
                        for i, (_, url) in enumerate(sheet_links)
                    )
                    + "</Relationships>",
                )
        archive.writestr(
            "xl/workbook.xml",
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            f'<sheets>{"".join(entries)}</sheets></workbook>',
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            + "".join(rels)
            + "</Relationships>",
        )
        archive.writestr(
            "xl/sharedStrings.xml",
            '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            + "".join(f"<si><t>{escape(text)}</t></si>" for text in strings)
            + "</sst>",
        )
    return buffer.getvalue()


class ReaderTest(unittest.TestCase):
    def test_values_ticks_and_links(self) -> None:
        sheet = read_workbook(make_xlsx({"Short Form": CALENDAR}, LINKS))[0]
        self.assertEqual(sheet.cell(1, 4).text, "Video Topic")
        self.assertEqual(as_date(sheet.cell(2, 1)), date(2026, 9, 3))
        self.assertIs(sheet.cell(2, 6).value, True)
        self.assertEqual(sheet.cell(2, 5).link, "https://www.instagram.com/reel/abc/")

    def test_dates_and_ticks_from_text(self) -> None:
        self.assertEqual(as_date(Cell("01-Oct-26")), date(2026, 10, 1))
        self.assertEqual(as_date(Cell("28-05-2026")), date(2026, 5, 28))
        self.assertTrue(is_ticked(Cell("posted")))
        self.assertFalse(is_ticked(Cell("Not posted")))
        self.assertFalse(is_ticked(Cell(None)))

    def test_not_an_xlsx(self) -> None:
        with self.assertRaises(ValueError):
            read_workbook(b"plain text")


class ParseTest(unittest.TestCase):
    def test_calendar_rows(self) -> None:
        parsed = parse(read_workbook(make_xlsx({"Short Form": CALENDAR}, LINKS)), "x.xlsx")
        rows = parsed.calendar["Short Form"]
        self.assertEqual(
            [row.title for row in rows], ["Keyboard Shortcuts", "No Reel", "Planned reel"]
        )
        first, no_reel, planned = rows
        self.assertEqual(first.reference_url, "https://www.instagram.com/reel/abc/")
        self.assertEqual(first.script_url, "https://docs.google.com/document/d/xyz/edit")
        self.assertIn("Script: Window keys", first.notes)
        self.assertTrue(first.recorded and first.edited)
        self.assertFalse(first.script_ready)
        self.assertTrue(no_reel.no_post)
        # Only a weekday: the next Tuesday after Sat 5 Sep 2026.
        self.assertEqual(planned.day, date(2026, 9, 8))
        self.assertEqual(parsed.tabs[0].skipped, 1)  # the idea without any date

    def test_budget_and_work_log(self) -> None:
        workbook = make_xlsx({"Dashboard": DASHBOARD, "Timesheet": TIMESHEET}, {})
        parsed = parse(read_workbook(workbook), "Vikas 01-Oct- 02-Nov - Dashboard.xlsx")
        self.assertEqual(
            [(p.day, p.amount) for p in parsed.payments], [(date(2026, 10, 1), Decimal("22000.0"))]
        )
        self.assertEqual(
            [(w.day, w.label, w.count, w.amount) for w in parsed.works],
            [
                (date(2026, 10, 1), "Slice Promotion", 2, Decimal("1400.0")),
                (date(2026, 10, 3), "Carousel", 1, Decimal("700.0")),
            ],
        )
        kinds = {tab.name: tab.kind for tab in parsed.tabs}
        self.assertEqual(kinds, {"Dashboard": "BUDGET", "Timesheet": "WORK"})


class FakeTasks:
    def get_client(self, company_id: Any, client_id: Any) -> ClientRef:
        return ClientRef(client_id, "Vikas", "CLT-0001", "ACTIVE")


class FakeCalendar:
    def __init__(self) -> None:
        self.created: list[dict[str, Any]] = []

    def create(self, company_id: Any, client_id: Any, actor: Any, values: dict[str, Any]) -> Any:
        self.created.append(values)
        return uuid4()


class ApplyTest(unittest.TestCase):
    def test_only_the_admin(self) -> None:
        service = ImportService(FakeCalendar(), None, FakeTasks())  # type: ignore[arg-type]
        with self.assertRaises(AuthenticationError):
            service.preview(context("COMPANY_MANAGER", uuid4()), uuid4(), b"", "x.xlsx")

    def test_rows_already_there_are_skipped(self) -> None:
        calendar = FakeCalendar()
        service = ImportService(calendar, None, FakeTasks())  # type: ignore[arg-type]
        workbook = make_xlsx({"Short Form": CALENDAR}, LINKS)
        existing = {(date(2026, 9, 3), "keyboard shortcuts")}
        with patch.object(ImportService, "_calendar_keys", staticmethod(lambda *_: set(existing))):
            result = service.apply(
                context("COMPANY_ADMIN", uuid4()),
                uuid4(),
                workbook,
                "a.xlsx",
                ["Short Form"],
                False,
            )
        self.assertEqual((result.calendar_added, result.calendar_skipped), (2, 1))
        self.assertEqual([row["title"] for row in calendar.created], ["No Reel", "Planned reel"])
        self.assertTrue(calendar.created[0]["no_post"])

    def test_wrong_file_type(self) -> None:
        service = ImportService(FakeCalendar(), None, FakeTasks())  # type: ignore[arg-type]
        with self.assertRaises(AuthenticationError) as refused:
            service.preview(context("COMPANY_ADMIN", uuid4()), uuid4(), b"x", "calendar.csv")
        self.assertEqual(refused.exception.code, "XLSX_REQUIRED")


if __name__ == "__main__":
    unittest.main()


def make_pdf() -> bytes:
    """A one-page PDF laid out like a Google Sheets export: a calendar table and a dashboard."""
    from reportlab.lib.pagesizes import landscape
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    page = canvas.Canvas(buffer, pagesize=landscape((595, 842)))
    page.setFont("Helvetica", 9)
    page.drawString(40, 560, "Client Budget")
    page.drawString(44, 545, "₹12,000".replace("₹", "Rs "))
    page.drawString(160, 560, "Selected Date")
    page.drawString(164, 545, "02-Nov-26")
    page.drawString(280, 560, "Amount Used")
    page.drawString(284, 545, "Rs 2,100")
    headers = [
        (40, "Date"),
        (120, "Day"),
        (200, "Video Topic"),
        (330, "Reference Video"),
        (460, "Youtube Posted"),
    ]
    for x, text in headers:
        page.drawString(x, 500, text)
    rows = [
        ("09-11-2026", "Monday", "Gold reel", "https://www.instagram.com/reel/gold/", "posted"),
        ("10-11-2026", "Tuesday", "PF reel", "Link", "Not posted"),
    ]
    for number, (day, weekday, topic, reference, posted) in enumerate(rows):
        y = 480 - number * 18
        page.drawString(38, y, day)
        page.drawString(118, y, weekday)
        page.drawString(205, y, topic)
        page.drawString(300, y, reference)
        page.drawString(462, y, posted)
        if reference == "Link":
            page.linkURL("https://docs.google.com/document/d/pf", (298, y - 2, 330, y + 9))
    page.drawString(40, 400, "Date")
    page.drawString(120, 400, "Videos")
    page.drawString(200, 400, "Amount")
    page.drawString(280, 400, "Budget Left")
    page.drawString(40, 382, "09-Nov-26")
    page.drawString(124, 382, "2")
    page.drawString(204, 382, "Rs 1,400")
    page.drawString(284, 382, "Rs 10,600")
    page.save()
    return buffer.getvalue()


class PdfImportTest(unittest.TestCase):
    def test_calendar_dashboard_and_links_from_a_pdf(self) -> None:
        from app.services.pdf_reader import read_pdf

        parsed = parse(read_pdf(make_pdf()), "Demo 02-Nov - Dashboard.pdf")
        rows = next(iter(parsed.calendar.values()))
        self.assertEqual([row.title for row in rows], ["Gold reel", "PF reel"])
        self.assertEqual(rows[0].reference_url, "https://www.instagram.com/reel/gold/")
        self.assertEqual(rows[1].reference_url, "https://docs.google.com/document/d/pf")
        self.assertEqual([row.posted_youtube for row in rows], [True, False])
        self.assertEqual(
            [(p.day, p.amount) for p in parsed.payments], [(date(2026, 11, 2), Decimal("12000.0"))]
        )
        # The latest day as listed, and the rest of Amount Used as one earlier line.
        self.assertEqual(
            [(w.day, w.label, w.count, w.amount) for w in parsed.works],
            [
                (date(2026, 11, 2), "Earlier work", 1, Decimal("700.0")),
                (date(2026, 11, 9), "Work delivered", 2, Decimal("1400.0")),
            ],
        )

    def test_a_pdf_upload_is_accepted(self) -> None:
        service = ImportService(FakeCalendar(), None, FakeTasks())  # type: ignore[arg-type]
        preview = service.preview(context("COMPANY_ADMIN", uuid4()), uuid4(), make_pdf(), "a.pdf")
        self.assertTrue(any(tab.kind == "CALENDAR" for tab in preview.tabs))

    def test_a_broken_pdf_is_refused_clearly(self) -> None:
        service = ImportService(FakeCalendar(), None, FakeTasks())  # type: ignore[arg-type]
        with self.assertRaises(AuthenticationError) as refused:
            service.preview(context("COMPANY_ADMIN", uuid4()), uuid4(), b"%PDF-broken", "a.pdf")
        self.assertEqual(refused.exception.code, "XLSX_UNREADABLE")
