"""A small, dependency-free reader for .xlsx files (owner request 2026-11-19: import the content
calendar and payment spreadsheets the team keeps in Excel / Google Sheets).

An .xlsx file is a zip of XML parts. This reads cell values (text, numbers, booleans, formula
results) and cell hyperlinks (from the sheet's hyperlink list or a HYPERLINK() formula), which
is all an import needs. Limits keep a hostile upload small: the file, every part, and the number
of rows read.
"""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from xml.etree import ElementTree

MAX_FILE_BYTES = 15 * 1024 * 1024
MAX_PART_BYTES = 60 * 1024 * 1024
MAX_ROWS = 5000

_MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_PKG_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"
_CELL = re.compile(r"^([A-Z]+)(\d+)$")
_HYPERLINK_FORMULA = re.compile(r'HYPERLINK\(\s*"([^"]+)"', re.IGNORECASE)


class XlsxError(ValueError):
    """The upload is not a readable .xlsx file."""


@dataclass
class Cell:
    value: str | float | bool | None = None
    link: str | None = None

    @property
    def text(self) -> str:
        if self.value is None:
            return ""
        if isinstance(self.value, bool):
            return "TRUE" if self.value else "FALSE"
        if isinstance(self.value, float):
            return str(int(self.value)) if self.value.is_integer() else str(self.value)
        return str(self.value).strip()


@dataclass
class Sheet:
    name: str
    # rows[row number][column number] (both 1-based), only cells that have something in them.
    rows: dict[int, dict[int, Cell]] = field(default_factory=dict)

    def cell(self, row: int, column: int) -> Cell:
        return self.rows.get(row, {}).get(column, Cell())


def column_number(letters: str) -> int:
    number = 0
    for char in letters:
        number = number * 26 + (ord(char) - 64)
    return number


def _split(reference: str) -> tuple[int, int] | None:
    match = _CELL.match(reference.split(":")[0].replace("$", ""))
    if not match:
        return None
    return int(match.group(2)), column_number(match.group(1))


def _read(archive: zipfile.ZipFile, name: str) -> bytes:
    try:
        info = archive.getinfo(name)
    except KeyError:
        return b""
    if info.file_size > MAX_PART_BYTES:
        raise XlsxError("The spreadsheet is too large to import.")
    return archive.read(info)


def _target(base: str, target: str) -> str:
    if target.startswith("/"):
        return target.lstrip("/")
    folder = base.rsplit("/", 1)[0]
    parts: list[str] = []
    for piece in f"{folder}/{target}".split("/"):
        if piece == "..":
            if parts:
                parts.pop()
        elif piece and piece != ".":
            parts.append(piece)
    return "/".join(parts)


def _relations(archive: zipfile.ZipFile, part: str) -> dict[str, tuple[str, str]]:
    folder, _, file = part.rpartition("/")
    data = _read(archive, f"{folder}/_rels/{file}.rels")
    if not data:
        return {}
    out: dict[str, tuple[str, str]] = {}
    for rel in ElementTree.fromstring(data).iter(f"{_PKG_REL}Relationship"):
        out[rel.get("Id", "")] = (rel.get("Target", ""), rel.get("TargetMode", ""))
    return out


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    data = _read(archive, "xl/sharedStrings.xml")
    if not data:
        return []
    return [
        "".join(node.text or "" for node in item.iter(f"{_MAIN}t"))
        for item in ElementTree.fromstring(data).iter(f"{_MAIN}si")
    ]


def read_workbook(content: bytes) -> list[Sheet]:
    """Every sheet of the workbook with its cells and links."""
    if len(content) > MAX_FILE_BYTES:
        raise XlsxError("The spreadsheet is too large to import (15 MB at most).")
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile as error:
        raise XlsxError(
            "This is not an .xlsx file. In Google Sheets use File → Download → .xlsx."
        ) from error
    with archive:
        workbook = _read(archive, "xl/workbook.xml")
        if not workbook:
            raise XlsxError(
                "This is not an .xlsx file. In Google Sheets use File → Download → .xlsx."
            )
        strings = _shared_strings(archive)
        relations = _relations(archive, "xl/workbook.xml")
        sheets: list[Sheet] = []
        for node in ElementTree.fromstring(workbook).iter(f"{_MAIN}sheet"):
            target = relations.get(node.get(f"{_REL}id", ""), ("", ""))[0]
            if not target:
                continue
            part = _target("xl/workbook.xml", target)
            sheets.append(_sheet(archive, node.get("name", "Sheet"), part, strings))
        return sheets


def _sheet(archive: zipfile.ZipFile, name: str, part: str, strings: list[str]) -> Sheet:
    sheet = Sheet(name=name)
    data = _read(archive, part)
    if not data:
        return sheet
    root = ElementTree.fromstring(data)
    for row in root.iter(f"{_MAIN}row"):
        for item in row.iter(f"{_MAIN}c"):
            place = _split(item.get("r", ""))
            if place is None or place[0] > MAX_ROWS:
                continue
            kind = item.get("t", "n")
            raw = item.find(f"{_MAIN}v")
            formula = item.find(f"{_MAIN}f")
            value: str | float | bool | None = None
            if kind == "s" and raw is not None and raw.text is not None:
                index = int(raw.text)
                value = strings[index] if index < len(strings) else ""
            elif kind == "inlineStr":
                value = "".join(node.text or "" for node in item.iter(f"{_MAIN}t"))
            elif kind == "b" and raw is not None:
                value = raw.text == "1"
            elif kind in {"str", "e"} and raw is not None:
                value = raw.text
            elif raw is not None and raw.text not in (None, ""):
                try:
                    value = float(raw.text or "")
                except ValueError:
                    value = raw.text
            link = None
            if formula is not None and formula.text:
                match = _HYPERLINK_FORMULA.search(formula.text)
                link = match.group(1) if match else None
            if value in (None, "") and link is None:
                continue
            sheet.rows.setdefault(place[0], {})[place[1]] = Cell(value, link)
    links = _relations(archive, part)
    for node in root.iter(f"{_MAIN}hyperlink"):
        place = _split(node.get("ref", ""))
        target = links.get(node.get(f"{_REL}id", ""), ("", ""))[0]
        if place is None or not target:
            continue
        cell = sheet.rows.setdefault(place[0], {}).setdefault(place[1], Cell())
        cell.link = target
    return sheet


_MONTHS = {
    name: index
    for index, names in enumerate(
        [
            ("jan", "january"),
            ("feb", "february"),
            ("mar", "march"),
            ("apr", "april"),
            ("may",),
            ("jun", "june"),
            ("jul", "july"),
            ("aug", "august"),
            ("sep", "sept", "september"),
            ("oct", "october"),
            ("nov", "november"),
            ("dec", "december"),
        ],
        start=1,
    )
    for name in names
}


def as_date(cell: Cell) -> date | None:
    """A date from an Excel serial number or text like 28-05-2026, 01-Oct-26, 2026-05-28."""
    value = cell.value
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, float):
        if 20000 < value < 80000:  # 1954 .. 2119
            return date(1899, 12, 30) + timedelta(days=int(value))
        return None
    text = str(value).strip()
    for pattern in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d.%m.%Y", "%d-%m-%y", "%d/%m/%y"):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            pass
    match = re.match(r"^(\d{1,2})[-\s/]([A-Za-z]{3,9})[-\s/,]*(\d{2,4})$", text)
    if match and match.group(2).lower() in _MONTHS:
        year = int(match.group(3))
        year += 2000 if year < 100 else 0
        try:
            return date(year, _MONTHS[match.group(2).lower()], int(match.group(1)))
        except ValueError:
            return None
    return None


def as_number(cell: Cell) -> float | None:
    """A number from a numeric cell or text like "₹1,400" / "Rs 700"."""
    value = cell.value
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, float):
        return value
    cleaned = re.sub(r"[^\d.\-]", "", str(value))
    try:
        return float(cleaned) if cleaned not in ("", "-", ".") else None
    except ValueError:
        return None


def is_ticked(cell: Cell) -> bool:
    """A tick box or a yes-like word ("done", "posted"); "not posted" is not a tick."""
    value = cell.value
    if isinstance(value, bool):
        return value
    if isinstance(value, float):
        return value == 1
    text = str(value or "").strip().lower()
    if not text or text.startswith(("not", "no ", "pending", "to be")):
        return False
    return text in {"1", "true", "yes", "y", "done", "posted", "completed", "✓", "✔", "x"} or (
        "posted" in text or "done" in text
    )
