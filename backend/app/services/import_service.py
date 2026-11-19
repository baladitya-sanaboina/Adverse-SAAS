"""Import a client's spreadsheets (owner request 2026-11-19: "client spreadsheets and payment
spreadsheets import chesela undali ... same mana format lo ne undali").

One upload is read for one client, shown as a preview first, and saved only when the admin
confirms:
- Content calendar tabs (Date | Week | Day | Video Topic | Reference | Recorded | Script | Edited |
  Insta-Posted | Youtube-Post | Script | PDF links) become calendar entries, ticks and links
  included. Old rows do not open tasks.
- A payment dashboard's "Client Budget" becomes a client payment (it opens a payment sheet).
- A work log (Date | Work | Videos | Rate | Amount) becomes delivered work: one completed task per
  row, dated on its day, so the sheets show the same Used and Left as the spreadsheet.
Running the same file twice adds nothing new: rows that are already there are skipped.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from app.database.connectivity import database_pool
from app.repositories.calendar_repository import CalendarRepository
from app.repositories.finance_repository import FinanceRepository
from app.repositories.task_repository import TaskRepository
from app.schemas.authentication import AuthContext
from app.schemas.imports import ImportMoneyLine, ImportPreview, ImportResult, ImportTab
from app.schemas.production import NamedRef
from app.services.authentication_service import AuthenticationError
from app.services.xlsx_reader import (
    Cell,
    Sheet,
    XlsxError,
    as_date,
    as_number,
    is_ticked,
    read_workbook,
)

logger = logging.getLogger(__name__)

_NO_POST = re.compile(
    r"^(no\s+(reel|post|video|upload)s?|skipped|missed|delayed|holiday|leave)\b", re.IGNORECASE
)
_FILLER = {"link", "links", "no need", "no need!!", "done", "not required", "posted", "-", "nil"}


@dataclass
class CalendarRow:
    day: date
    title: str
    reference_url: str = ""
    script_url: str = ""
    pdf_url: str = ""
    notes: str = ""
    no_post: bool = False
    recorded: bool = False
    script_ready: bool = False
    edited: bool = False
    posted_instagram: bool = False
    posted_youtube: bool = False


@dataclass
class MoneyRow:
    day: date
    label: str
    amount: Decimal
    count: int = 1


@dataclass
class Parsed:
    tabs: list[ImportTab] = field(default_factory=list)
    calendar: dict[str, list[CalendarRow]] = field(default_factory=dict)
    payments: list[MoneyRow] = field(default_factory=list)
    works: list[MoneyRow] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# -- reading -----------------------------------------------------------------------------------


def _header(sheet: Sheet) -> tuple[int, dict[int, str]] | None:
    """The first row (within the top 12) that has a "Date" heading."""
    for number in sorted(sheet.rows)[:12]:
        texts = {
            column: cell.text.lower()
            for column, cell in sheet.rows[number].items()
            if isinstance(cell.value, str)
        }
        if any(text == "date" or text.startswith("date") for text in texts.values()):
            return number, texts
    return None


def _url(cell: Cell) -> str:
    if cell.link and cell.link.lower().startswith(("http://", "https://")):
        return cell.link[:1000]
    text = cell.text
    return text[:1000] if text.lower().startswith(("http://", "https://")) else ""


def _note(label: str, cell: Cell) -> str:
    text = cell.text
    if not text or _url(cell) == text or text.lower() in _FILLER or text.strip("-! ") == "":
        return ""
    return f"{label}: {text}"


def _calendar_columns(sheet: Sheet, row: int, texts: dict[int, str]) -> dict[str, Any] | None:
    columns: dict[str, Any] = {"script_ticks": [], "links": []}
    for column, text in sorted(texts.items()):
        if text == "date" or text.startswith("date"):
            columns.setdefault("date", column)
        elif text in {"day", "weekday"}:
            columns.setdefault("weekday", column)
        elif "topic" in text or text in {"title", "video title", "video"}:
            columns.setdefault("title", column)
        elif "reference" in text:
            columns.setdefault("reference", column)
        elif "record" in text:
            columns.setdefault("recorded", column)
        elif "insta" in text:
            columns.setdefault("insta", column)
        elif "youtube" in text or text in {"yt", "yt-post"}:
            columns.setdefault("youtube", column)
        elif "pdf" in text:
            columns.setdefault("pdf", column)
        elif "resource" in text:
            columns["links"].append(("Resources", column))
        elif "edit" in text:
            columns.setdefault("edited", column)
        elif "script" in text:
            data = [sheet.rows.get(number, {}).get(column) for number in sheet.rows if number > row]
            wordy = any(
                cell is not None
                and (
                    cell.link
                    or (isinstance(cell.value, str) and cell.text.upper() not in {"TRUE", "FALSE"})
                )
                for cell in data
            )
            (columns["links"] if wordy else columns["script_ticks"]).append(("Script", column))
    if "date" not in columns or "title" not in columns:
        return None
    signals = {"reference", "recorded", "insta", "youtube", "edited", "pdf"}
    return columns if signals & set(columns) else None


_WEEKDAYS = {
    name: index
    for index, names in enumerate(
        [
            ("monday", "mon"),
            ("tuesday", "tue", "tues"),
            ("wednesday", "wed"),
            ("thursday", "thu", "thur", "thurs"),
            ("friday", "fri"),
            ("saturday", "sat"),
            ("sunday", "sun"),
        ]
    )
    for name in names
}


def _next_weekday(after: date, name: str) -> date | None:
    """The first date after `after` that falls on the named weekday ("Thursday --> Friday" uses
    the last name)."""
    words = re.findall(r"[a-z]+", name.lower())
    wanted = next((_WEEKDAYS[word] for word in reversed(words) if word in _WEEKDAYS), None)
    if wanted is None:
        return None
    step = (wanted - after.weekday()) % 7 or 7
    return date.fromordinal(after.toordinal() + step)


def _calendar(
    sheet: Sheet, row: int, columns: dict[str, Any]
) -> tuple[list[CalendarRow], int, list[str]]:
    out: list[CalendarRow] = []
    skipped = 0
    seen: set[tuple[date, str]] = set()
    previous: date | None = None
    for number in sorted(sheet.rows):
        if number <= row:
            continue

        def get(key: str, number: int = number) -> Cell:
            return sheet.cell(number, columns[key]) if key in columns else Cell()

        title = get("title").text[:200]
        day = as_date(get("date"))
        if day is not None and not 2000 <= day.year <= 2100:
            day = None  # a typo such as 12-09-0202
        if day is None and previous is not None and get("weekday").text:
            # A planned row with only its weekday: the next such day after the row above.
            day = _next_weekday(previous, get("weekday").text)
        if day is not None:
            previous = day
        if not title:
            continue
        if day is None:
            skipped += 1
            continue
        key = (day, title.lower())
        if key in seen:
            continue
        seen.add(key)
        entry = CalendarRow(day=day, title=title)
        entry.no_post = bool(_NO_POST.match(title))
        entry.reference_url = _url(get("reference"))
        notes = [_note("Reference", get("reference"))]
        entry.pdf_url = _url(get("pdf"))
        notes.append(_note("PDF", get("pdf")))
        for label, column in columns["links"]:
            cell = sheet.cell(number, column)
            if not entry.script_url and _url(cell):
                entry.script_url = _url(cell)
                if cell.text and cell.text != entry.script_url and cell.text.lower() not in _FILLER:
                    notes.append(f"{label}: {cell.text}")
            else:
                notes.append(_note(label, cell))
        entry.notes = "\n".join(note for note in notes if note)[:2000]
        entry.recorded = is_ticked(get("recorded"))
        entry.edited = is_ticked(get("edited"))
        entry.posted_instagram = is_ticked(get("insta"))
        entry.posted_youtube = is_ticked(get("youtube"))
        entry.script_ready = any(
            is_ticked(sheet.cell(number, column)) for _, column in columns["script_ticks"]
        )
        out.append(entry)
    sample = [f"{item.day:%d %b %Y} · {item.title}" for item in out[:3]]
    return out, skipped, sample


def _work_columns(texts: dict[int, str], summary: bool = False) -> dict[str, int] | None:
    """A work log's columns. A table with a "Budget Left" column is the dashboard's day summary
    (Recent Dates): only read when `summary` is asked for (a PDF dashboard has nothing else)."""
    if not summary and any("budget left" in text or "balance" in text for text in texts.values()):
        return None
    columns: dict[str, int] = {}
    for column, text in sorted(texts.items()):
        if text == "date" or text.startswith("date"):
            columns.setdefault("date", column)
        elif text in {"videos", "no of videos", "no. of videos", "count", "qty", "quantity", "nos"}:
            columns.setdefault("count", column)
        elif "budget left" in text or "balance" in text:
            continue
        elif "amount" in text or text in {"total", "total amount"}:
            columns.setdefault("amount", column)
        elif "rate" in text or text in {"price", "per video"}:
            columns.setdefault("rate", column)
        elif any(
            word in text
            for word in ("work", "title", "topic", "details", "description", "name", "video")
        ):
            columns.setdefault("title", column)
    if "date" not in columns or not ({"amount", "rate"} & set(columns)):
        return None
    return columns


def _works(sheet: Sheet, row: int, columns: dict[str, int]) -> tuple[list[MoneyRow], int]:
    out: list[MoneyRow] = []
    skipped = 0
    for number in sorted(sheet.rows):
        if number <= row:
            continue

        def cell(key: str, number: int = number) -> Cell:
            return sheet.cell(number, columns[key]) if key in columns else Cell()

        day = as_date(cell("date"))
        count = int(as_number(cell("count")) or 1)
        amount = as_number(cell("amount"))
        if amount is None and as_number(cell("rate")) is not None:
            amount = (as_number(cell("rate")) or 0) * count
        if day is None or not amount or amount <= 0:
            if any(c.text for c in sheet.rows[number].values()):
                skipped += 1
            continue
        title = cell("title").text[:180] or "Video"
        out.append(
            MoneyRow(
                day=day, label=title, amount=Decimal(str(round(amount, 2))), count=max(count, 1)
            )
        )
    return out, skipped


def _labelled(sheet: Sheet, label: str) -> Cell | None:
    """The value under (or next to) a dashboard label such as "Client Budget"."""
    for number in sorted(sheet.rows):
        for column, cell in sheet.rows[number].items():
            if cell.text.lower() == label:
                for candidate in (sheet.cell(number + 1, column), sheet.cell(number, column + 1)):
                    if candidate.text and candidate.text.lower() != label:
                        return candidate
    return None


def _date_from_name(file_name: str, year_hint: int) -> date | None:
    match = re.search(r"(\d{1,2})[-\s]([A-Za-z]{3,9})(?:[-\s](\d{2,4}))?", file_name)
    if not match:
        return None
    return as_date(Cell(f"{match.group(1)}-{match.group(2)}-{match.group(3) or year_hint}"))


def _summary_works(
    parsed: Parsed, sheets: list[Sheet], summaries: list[MoneyRow], start: date
) -> None:
    """A dashboard without a work log (e.g. its PDF) shows only the latest days and the totals.
    Those days are added as they are, and the rest of "Amount Used" as one "Earlier work" line on
    the budget date, so Used and Left in Adverse match the dashboard."""
    used_cell = next((cell for sheet in sheets if (cell := _labelled(sheet, "amount used"))), None)
    videos_cell = next(
        (cell for sheet in sheets if (cell := _labelled(sheet, "total videos"))), None
    )
    used = Decimal(str(as_number(used_cell) or 0)) if used_cell else None
    days = sorted(
        {(item.day, item.label, item.amount): item for item in summaries}.values(),
        key=lambda item: item.day,
    )
    for item in days:
        item.label = "Work delivered" if item.label == "Video" else item.label
    shown = sum((item.amount for item in days), Decimal("0"))
    if used is not None and used > shown:
        total_videos = int(as_number(videos_cell) or 0) if videos_cell else 0
        earlier_videos = max(total_videos - sum(item.count for item in days), 1)
        parsed.works.append(
            MoneyRow(
                day=start,
                label="Earlier work",
                amount=used - shown,
                count=earlier_videos,
            )
        )
        parsed.warnings.append(
            "The dashboard lists only its latest days; the rest of Amount Used is added as one "
            "'Earlier work' line on the budget date."
        )
    parsed.works += days
    if parsed.works:
        parsed.tabs.append(
            ImportTab(
                name="Dashboard days",
                kind="WORK",
                rows=len(parsed.works),
                skipped=0,
                first_day=min(item.day for item in parsed.works),
                last_day=max(item.day for item in parsed.works),
                sample=[f"{item.day:%d %b %Y} · {item.label}" for item in parsed.works[:3]],
            )
        )


def parse(sheets: list[Sheet], file_name: str) -> Parsed:
    parsed = Parsed()
    budget_cell: tuple[Sheet, Cell] | None = None
    summaries: list[MoneyRow] = []
    for sheet in sheets:
        header = _header(sheet)
        if header is not None:
            row, texts = header
            calendar_columns = _calendar_columns(sheet, row, texts)
            if calendar_columns is not None:
                rows, skipped, sample = _calendar(sheet, row, calendar_columns)
                parsed.calendar[sheet.name] = rows
                parsed.tabs.append(
                    ImportTab(
                        name=sheet.name,
                        kind="CALENDAR",
                        rows=len(rows),
                        skipped=skipped,
                        first_day=min((item.day for item in rows), default=None),
                        last_day=max((item.day for item in rows), default=None),
                        sample=sample,
                    )
                )
                if skipped:
                    parsed.warnings.append(
                        f"{sheet.name}: {skipped} rows have no date and will be left out."
                    )
                continue
            work_columns = _work_columns(texts)
            if work_columns is not None:
                works, skipped = _works(sheet, row, work_columns)
                if works:
                    parsed.works += works
                    parsed.tabs.append(
                        ImportTab(
                            name=sheet.name,
                            kind="WORK",
                            rows=len(works),
                            skipped=skipped,
                            first_day=min(item.day for item in works),
                            last_day=max(item.day for item in works),
                            sample=[f"{item.day:%d %b %Y} · {item.label}" for item in works[:3]],
                        )
                    )
                    continue
            summary_columns = _work_columns(texts, summary=True)
            if summary_columns is not None:
                found, _ = _works(sheet, row, summary_columns)
                summaries += found
        budget = _labelled(sheet, "client budget")
        if budget is not None and as_number(budget):
            budget_cell = (sheet, budget)
            parsed.tabs.append(ImportTab(name=sheet.name, kind="BUDGET", rows=1, skipped=0))
            continue
        parsed.tabs.append(ImportTab(name=sheet.name, kind="OTHER", rows=0, skipped=0))
    if budget_cell is not None:
        sheet, cell = budget_cell
        picked = _labelled(sheet, "selected date")
        day = as_date(picked) if picked else None
        year = min((item.day.year for item in parsed.works), default=date.today().year)
        day = day or _date_from_name(file_name, year)
        if day is None and parsed.works:
            day = min(item.day for item in parsed.works)
            parsed.warnings.append("The budget has no date; it is dated on the first work day.")
        if day is not None:
            parsed.payments.append(
                MoneyRow(day=day, label="Client budget", amount=Decimal(str(as_number(cell))))
            )
            if not parsed.works:
                _summary_works(parsed, sheets, summaries, day)
        else:
            parsed.warnings.append("The budget has no date, so it cannot be imported.")
    if not parsed.calendar and not parsed.works and not parsed.payments:
        parsed.warnings.append(
            "Nothing to import was found. The calendar needs Date and Video Topic headings; a "
            "work log needs Date and Amount (or Rate) headings."
        )
    return parsed


# -- saving ------------------------------------------------------------------------------------


class ImportService:
    def __init__(
        self,
        calendar: CalendarRepository | None = None,
        finance: FinanceRepository | None = None,
        tasks: TaskRepository | None = None,
    ) -> None:
        self.calendar = calendar or CalendarRepository()
        self.finance = finance or FinanceRepository()
        self.tasks = tasks or TaskRepository()

    def _client(self, context: AuthContext, client_id: UUID) -> tuple[UUID, NamedRef]:
        if context.role != "COMPANY_ADMIN" or context.company_id is None:
            raise AuthenticationError(
                403, "COMPANY_ADMIN_REQUIRED", "Only the Company Admin can import spreadsheets."
            )
        client = self.tasks.get_client(context.company_id, client_id)
        if client is None:
            raise AuthenticationError(404, "CLIENT_NOT_FOUND", "Client was not found.")
        return context.company_id, NamedRef(id=client.id, name=client.name, code=client.code)

    @staticmethod
    def _read(content: bytes, file_name: str) -> Parsed:
        name = file_name.lower()
        if not name.endswith((".xlsx", ".pdf")):
            raise AuthenticationError(
                422,
                "XLSX_REQUIRED",
                "Upload an .xlsx or a .pdf file. From Google Sheets: File → Download.",
            )
        try:
            if name.endswith(".pdf"):
                from app.services.pdf_reader import read_pdf

                return parse(read_pdf(content), file_name)
            return parse(read_workbook(content), file_name)
        except XlsxError as error:
            raise AuthenticationError(422, "XLSX_UNREADABLE", str(error)) from error

    def preview(
        self, context: AuthContext, client_id: UUID, content: bytes, file_name: str
    ) -> ImportPreview:
        _, client = self._client(context, client_id)
        parsed = self._read(content, file_name)
        return ImportPreview(
            client=client,
            file_name=file_name,
            tabs=parsed.tabs,
            payments=[_line(item) for item in parsed.payments],
            works=[_line(item) for item in parsed.works],
            paid_total=sum((item.amount for item in parsed.payments), Decimal("0")),
            work_total=sum((item.amount for item in parsed.works), Decimal("0")),
            warnings=parsed.warnings,
        )

    def apply(
        self,
        context: AuthContext,
        client_id: UUID,
        content: bytes,
        file_name: str,
        tabs: list[str],
        money: bool,
    ) -> ImportResult:
        company_id, client = self._client(context, client_id)
        parsed = self._read(content, file_name)
        actor = context.user_id
        added = skipped = 0
        existing = self._calendar_keys(company_id, client.id)
        for name in tabs:
            for row in parsed.calendar.get(name, []):
                key = (row.day, row.title.lower())
                if key in existing:
                    skipped += 1
                    continue
                existing.add(key)
                self.calendar.create(
                    company_id,
                    client.id,
                    actor,
                    {
                        "entry_date": row.day,
                        "title": row.title,
                        "reference_url": row.reference_url,
                        "script_url": row.script_url,
                        "pdf_url": row.pdf_url,
                        "notes": row.notes,
                        "no_post": row.no_post,
                        "recorded": row.recorded,
                        "script_ready": row.script_ready,
                        "posted_instagram": row.posted_instagram,
                        "posted_youtube": row.posted_youtube,
                        "edited_manual": row.edited,
                    },
                )
                added += 1
        paid_added = paid_skipped = work_added = work_skipped = 0
        if money:
            for payment in parsed.payments:
                if self._payment_exists(company_id, client.id, payment):
                    paid_skipped += 1
                    continue
                self.finance.create_client_payment(
                    company_id,
                    actor,
                    {
                        "client_id": client.id,
                        "amount": payment.amount,
                        "received_on": payment.day,
                        "method": "OTHER",
                        "reference": f"Imported · {file_name}"[:120],
                        "note": "Imported from a spreadsheet.",
                    },
                )
                paid_added += 1
            service = self._service(company_id, client.id)
            if parsed.works and service is None:
                raise AuthenticationError(
                    422,
                    "NO_SERVICE",
                    "Add a service first (Settings → Services); imported work needs one.",
                )
            tz = ZoneInfo(self.finance.company_timezone(company_id))
            for work in parsed.works:
                title = work.label if work.count == 1 else f"{work.label} ×{work.count}"
                if self._work_exists(company_id, client.id, title, work, tz):
                    work_skipped += 1
                    continue
                assert service is not None
                self._create_work(company_id, actor, client.id, service, title, work, tz)
                work_added += 1
        parts = []
        if added or skipped:
            parts.append(
                f"{added} calendar rows added" + (f", {skipped} already there" if skipped else "")
            )
        if paid_added or paid_skipped:
            parts.append(
                f"{paid_added} payments added"
                + (f", {paid_skipped} already there" if paid_skipped else "")
            )
        if work_added or work_skipped:
            parts.append(
                f"{work_added} delivered videos added"
                + (f", {work_skipped} already there" if work_skipped else "")
            )
        return ImportResult(
            calendar_added=added,
            calendar_skipped=skipped,
            payments_added=paid_added,
            payments_skipped=paid_skipped,
            works_added=work_added,
            works_skipped=work_skipped,
            message=("; ".join(parts) or "Nothing new to import") + ".",
        )

    # -- small queries -----------------------------------------------------------------------

    @staticmethod
    def _calendar_keys(company_id: UUID, client_id: UUID) -> set[tuple[date, str]]:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT entry_date, LOWER(title) FROM content_calendar_entries "
                "WHERE company_id=%s AND client_id=%s",
                (company_id, client_id),
            )
            return {(row[0], row[1]) for row in cursor.fetchall()}

    @staticmethod
    def _payment_exists(company_id: UUID, client_id: UUID, payment: MoneyRow) -> bool:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM client_payments WHERE company_id=%s AND client_id=%s "
                "AND received_on=%s AND amount=%s LIMIT 1",
                (company_id, client_id, payment.day, payment.amount),
            )
            return cursor.fetchone() is not None

    @staticmethod
    def _work_exists(
        company_id: UUID, client_id: UUID, title: str, work: MoneyRow, tz: ZoneInfo
    ) -> bool:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM tasks WHERE company_id=%s AND client_id=%s AND LOWER(title)=LOWER(%s) "
                "AND client_price_final=%s AND approved_at IS NOT NULL "
                "AND ((approved_at AT TIME ZONE 'UTC') AT TIME ZONE %s)::date = %s LIMIT 1",
                (company_id, client_id, title, work.amount, str(tz), work.day),
            )
            return cursor.fetchone() is not None

    def _service(self, company_id: UUID, client_id: UUID) -> Any:
        for service_id in self.tasks.calendar_service_choices(company_id, client_id):
            service = self.tasks.get_service(company_id, service_id)
            if service is not None:
                return service
        return None

    def _create_work(
        self,
        company_id: UUID,
        actor: UUID,
        client_id: UUID,
        service: Any,
        title: str,
        work: MoneyRow,
        tz: ZoneInfo,
    ) -> None:
        """A delivered video from the spreadsheet: a completed task approved on its day."""
        task_id = self.tasks.create_task(
            company_id,
            actor,
            {
                "client_id": client_id,
                "service_id": service.id,
                "title": title[:200],
                "description": "Imported from a spreadsheet (work already delivered).",
                "priority": "MEDIUM",
                "status": "COMPLETED",
                "assignee_user_id": None,
                "assignee_type": None,
                "monitor_user_id": None,
                "due_date": work.day,
                "client_pricing_model": service.client_pricing_model,
                "client_price_default": work.amount,
                "client_price_final": work.amount,
                "client_price_reason": "Imported",
                "commission_default": None,
                "commission_final": None,
                "commission_reason": "",
                "assigned_at": None,
            },
            [],
        )
        moment = (
            datetime.combine(work.day, time(12, 0), tzinfo=tz)
            .astimezone(ZoneInfo("UTC"))
            .replace(tzinfo=None)
        )
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "UPDATE tasks SET submitted_at=%s, approved_at=%s, completed_at=%s WHERE id=%s "
                "AND company_id=%s",
                (moment, moment, moment, task_id, company_id),
            )


def _line(item: MoneyRow) -> ImportMoneyLine:
    return ImportMoneyLine(day=item.day, label=item.label, amount=item.amount, count=item.count)


import_service = ImportService()
