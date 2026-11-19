"""Read spreadsheet-like PDFs for the import (owner request 2026-11-19: "pdf files upload
chesukuni data tisukunela undali ... situation ela aina undochu").

A PDF has no cells, only text placed on the page. Each page is rebuilt into rows (text at the same
height) and columns (matched to the header row that has a "Date" heading, by position), so the
same importer that reads .xlsx files can read it. Pages without a header continue the table of
the page before. Links are taken from the PDF's link areas. Dashboard labels ("Client Budget",
"Selected Date", ...) are paired with the value printed under them.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from typing import Any

from app.services.xlsx_reader import MAX_FILE_BYTES, Cell, Sheet, XlsxError, as_date

logger = logging.getLogger(__name__)
MAX_PAGES = 60


@dataclass
class _Item:
    x: float  # left edge, page units
    y: float  # baseline, page units (up is larger)
    size: float
    text: str
    link: str | None = None

    @property
    def centre(self) -> float:
        return self.x + len(self.text) * self.size * 0.25


def _items(page: Any) -> list[_Item]:
    found: list[_Item] = []

    def visit(text: str, cm: list[float], tm: list[float], font: Any, size: float) -> None:
        value = text.strip()
        if not value:
            return
        x = cm[0] * tm[4] + cm[2] * tm[5] + cm[4]
        y = cm[1] * tm[4] + cm[3] * tm[5] + cm[5]
        scale = abs(cm[0]) or 1.0
        found.append(_Item(x=x, y=y, size=max(size * scale, 1.0), text=value))

    page.extract_text(visitor_text=visit)
    links = _links(page)
    for item in found:
        # The link area must cover this text's own line (its middle is a bit above the baseline).
        middle = item.y + item.size * 0.3
        best: tuple[float, str] | None = None
        for x0, y0, x1, y1, uri in links:
            if not (x0 - 2 <= item.x + item.size * 0.5 <= x1 + 2):
                continue
            if not (y0 - item.size * 0.25 <= middle <= y1 + item.size * 0.25):
                continue
            distance = abs((y0 + y1) / 2 - middle)
            if best is None or distance < best[0]:
                best = (distance, uri)
        if best is not None:
            item.link = best[1]
    return found


def _links(page: Any) -> list[tuple[float, float, float, float, str]]:
    out: list[tuple[float, float, float, float, str]] = []
    annots = page.get("/Annots")
    if annots is None:
        return out
    for ref in annots.get_object():
        try:
            note = ref.get_object()
            action = note.get("/A")
            action = action.get_object() if action is not None else None
            uri = action.get("/URI") if action is not None else None
            rect = [float(value) for value in note.get("/Rect")]
        except Exception:  # noqa: BLE001 - a broken annotation is skipped
            continue
        if uri:
            out.append(
                (
                    min(rect[0], rect[2]),
                    min(rect[1], rect[3]),
                    max(rect[0], rect[2]),
                    max(rect[1], rect[3]),
                    str(uri),
                )
            )
    return out


def _rows(items: list[_Item]) -> list[list[_Item]]:
    rows: list[list[_Item]] = []
    for item in sorted(items, key=lambda value: (-value.y, value.x)):
        if rows and abs(rows[-1][0].y - item.y) <= max(2.0, rows[-1][0].size * 0.45):
            rows[-1].append(item)
        else:
            rows.append([item])
    return [sorted(row, key=lambda value: value.x) for row in rows]


def _is_header(row: list[_Item]) -> bool:
    return len(row) >= 3 and any(
        item.text.lower() == "date" or item.text.lower().startswith("date ") for item in row
    )


def _column(anchors: list[_Item], item: _Item) -> int:
    """The column (1-based) of a piece of text: the header whose centre is nearest (cells are
    usually centred). A web address runs out of its cell, so it goes to the Reference / Link
    column it spans, when there is one."""

    def nearest(indexes: list[int]) -> int:
        return min(indexes, key=lambda index: abs(anchors[index].centre - item.centre))

    every = list(range(len(anchors)))
    if item.text.lower().startswith(("http://", "https://", "www.")):
        end = item.x + len(item.text) * item.size * 0.5
        spanned = [
            index for index in every if item.x - item.size * 2 <= anchors[index].centre <= end
        ]
        linky = [
            index
            for index in spanned
            if any(word in anchors[index].text.lower() for word in ("reference", "link", "url"))
        ]
        if linky:
            return 1 + nearest(linky)
    return 1 + nearest(every)


def _labels(pages: list[list[_Item]], name: str) -> Sheet:
    """Label / value pairs: each short text with the value printed just under it, on its page."""
    sheet = Sheet(name=name)
    row = 1
    for items in pages:
        row = _page_labels(items, sheet, row)
    return sheet


def _page_labels(items: list[_Item], sheet: Sheet, row: int) -> int:
    for label in items:
        if len(label.text) > 40:
            continue
        below = [
            other
            for other in items
            if other is not label
            and 0 < label.y - other.y <= label.size * 4.5
            and abs(other.centre - label.centre) <= max(60.0, label.size * 5)
        ]
        if not below:
            continue
        # The nearest one under it, preferring a figure (a number, amount or date).
        below.sort(key=lambda other: label.y - other.y)
        value = next((other for other in below if any(ch.isdigit() for ch in other.text)), below[0])
        sheet.rows[row] = {1: Cell(label.text)}
        sheet.rows[row + 1] = {1: Cell(value.text, value.link)}
        row += 3  # a blank row between pairs, so a value is never read as a label's answer
    return row


def read_pdf(content: bytes) -> list[Sheet]:
    """Tables (one sheet per table, continued across pages) and one sheet of label pairs."""
    if len(content) > MAX_FILE_BYTES:
        raise XlsxError("The PDF is too large to import (15 MB at most).")
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(content))
        pages = list(reader.pages)[:MAX_PAGES]
    except Exception as error:  # noqa: BLE001 - any parse failure is the same for the admin
        raise XlsxError(
            "This PDF could not be read. Export it again, or upload the .xlsx."
        ) from error
    sheets: list[Sheet] = []
    every: list[list[_Item]] = []
    anchors: list[_Item] | None = None
    table: Sheet | None = None
    next_row = 2
    previous: dict[int, Cell] | None = None
    for number, page in enumerate(pages, start=1):
        try:
            items = _items(page)
        except Exception:  # noqa: BLE001
            logger.warning("Could not read page %s of an imported PDF", number, exc_info=True)
            continue
        every.append(items)
        previous = None  # a wrapped cell never continues onto the next page
        for row in _rows(items):
            if _is_header(row):
                anchors = row
                table = Sheet(name=f"Table {len(sheets) + 1} (page {number})")
                table.rows[1] = {index + 1: Cell(item.text) for index, item in enumerate(anchors)}
                sheets.append(table)
                next_row, previous = 2, None
                continue
            if anchors is None or table is None:
                continue
            cells: dict[int, Cell] = {}
            for item in row:
                column = _column(anchors, item)
                if column in cells:
                    cells[column].value = f"{cells[column].text} {item.text}"
                    cells[column].link = cells[column].link or item.link
                else:
                    cells[column] = Cell(item.text, item.link)
            dated = 1 in cells and as_date(cells[1]) is not None
            weekday_column = next(
                (
                    index + 1
                    for index, item in enumerate(anchors)
                    if item.text.lower() in {"day", "weekday"}
                ),
                None,
            )
            planned = weekday_column is not None and weekday_column in cells
            if not dated and not planned and previous is None:
                continue  # page titles and notes around the table
            if not dated and not planned and previous is not None:
                # The second line of a wrapped cell: join it to the row above.
                for column, cell in cells.items():
                    if column in previous:
                        previous[column].value = f"{previous[column].text} {cell.text}"
                        previous[column].link = previous[column].link or cell.link
                    else:
                        previous[column] = cell
                continue
            table.rows[next_row] = cells
            previous = cells
            next_row += 1
    if not any(every):
        raise XlsxError("This PDF has no text to read (it may be a scanned image).")
    sheets.append(_labels(every, "Labels"))
    return sheets
