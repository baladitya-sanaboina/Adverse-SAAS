"""Spreadsheet import shapes (owner request 2026-11-19)."""

from datetime import date
from typing import Literal

from pydantic import BaseModel

from app.schemas.production import Money, NamedRef

TabKind = Literal["CALENDAR", "WORK", "BUDGET", "OTHER"]


class ImportTab(BaseModel):
    """One tab of the workbook and what it looks like to the importer."""

    name: str
    kind: TabKind
    rows: int  # rows that will be imported from it
    skipped: int  # rows left out (no date, or no title)
    first_day: date | None = None
    last_day: date | None = None
    sample: list[str] = []


class ImportMoneyLine(BaseModel):
    day: date
    label: str
    amount: Money
    count: int = 1


class ImportPreview(BaseModel):
    client: NamedRef
    file_name: str
    tabs: list[ImportTab]
    payments: list[ImportMoneyLine]
    works: list[ImportMoneyLine]
    paid_total: Money
    work_total: Money
    warnings: list[str] = []


class ImportResult(BaseModel):
    calendar_added: int
    calendar_skipped: int
    payments_added: int
    payments_skipped: int
    works_added: int
    works_skipped: int
    message: str
