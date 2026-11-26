"""Content calendar shapes (Phase 13)."""

from datetime import date, datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.production import NamedRef, TaskPriority
from app.services.production_rules import TaskStatus


def _strip(value: str) -> str:
    return value.strip()


def _check_url(value: str) -> str:
    """A web link. "docs.google.com/..." gets https:// added; plain words are refused clearly."""
    value = value.strip()
    if not value or value.lower().startswith(("http://", "https://")):
        return value
    host = value.split("/", 1)[0]
    if " " not in value and "." in host and not host.startswith(".") and not host.endswith("."):
        return f"https://{value}"
    raise ValueError(
        "Links must be web addresses, like https://docs.google.com/… (not plain text)."
    )


class CalendarTaskRef(BaseModel):
    id: UUID
    code: str
    title: str
    status: TaskStatus


class CalendarScriptRef(BaseModel):
    file_name: str
    size_bytes: int


class CalendarEntryResponse(BaseModel):
    id: UUID
    client: NamedRef
    entry_date: date
    title: str
    reference_url: str
    script_url: str
    pdf_url: str
    notes: str
    no_post: bool
    recorded: bool
    script_ready: bool
    posted_instagram: bool
    posted_youtube: bool
    # Ticks itself when the linked task is approved; the admin can also tick it by hand.
    edited: bool
    edited_manual: bool
    script: CalendarScriptRef | None
    task: CalendarTaskRef | None
    service: NamedRef | None = None  # Reel, Carousel, ... (owner request 2026-11-20)
    created_by_name: str
    created_at: datetime
    updated_at: datetime


class CalendarServiceOption(BaseModel):
    id: UUID
    name: str
    code: str


class CalendarListResponse(BaseModel):
    items: list[CalendarEntryResponse]


class CalendarEntryCreate(BaseModel):
    """A new entry. `client_id` is required from the admin and refused from a client."""

    model_config = ConfigDict(extra="forbid")

    client_id: UUID | None = None
    entry_date: date
    title: str = Field(min_length=1, max_length=200)
    reference_url: str = Field(default="", max_length=1000)
    script_url: str = Field(default="", max_length=1000)
    pdf_url: str = Field(default="", max_length=1000)
    notes: str = Field(default="", max_length=2000)
    no_post: bool = False
    # The priority of the task this entry opens (owner request 2026-11-19); empty = from the date.
    priority: TaskPriority | None = None
    # The service of the video (owner request 2026-11-20): required unless it is a no-post day.
    service_id: UUID | None = None

    _strip_text = field_validator("title", "notes")(_strip)
    _url = field_validator("reference_url", "script_url", "pdf_url")(_check_url)

    @model_validator(mode="after")
    def check_title(self) -> Self:
        if not self.title:
            raise ValueError("Title cannot be blank.")
        if not self.no_post and self.service_id is None:
            raise ValueError("Choose the service: Reel, Carousel, Thumbnail...")
        return self


class CalendarEntryUpdate(BaseModel):
    """Send only the fields that change. `edited_manual` is for the admin only."""

    model_config = ConfigDict(extra="forbid")

    entry_date: date | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)
    reference_url: str | None = Field(default=None, max_length=1000)
    script_url: str | None = Field(default=None, max_length=1000)
    pdf_url: str | None = Field(default=None, max_length=1000)
    notes: str | None = Field(default=None, max_length=2000)
    no_post: bool | None = None
    recorded: bool | None = None
    script_ready: bool | None = None
    posted_instagram: bool | None = None
    posted_youtube: bool | None = None
    edited_manual: bool | None = None
    service_id: UUID | None = None

    @field_validator("title", "notes")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("reference_url", "script_url", "pdf_url")
    @classmethod
    def check_url(cls, value: str | None) -> str | None:
        return _check_url(value) if value is not None else None

    @model_validator(mode="after")
    def check_title(self) -> Self:
        if self.title is not None and not self.title:
            raise ValueError("Title cannot be blank.")
        return self


class CalendarTaskLink(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: UUID | None


class StaffCalendarTask(BaseModel):
    id: UUID
    code: str
    title: str
    status: TaskStatus
    due_date: date
    client_name: str
    my_role: Literal["ASSIGNEE", "MONITOR"]


class StaffCalendarResponse(BaseModel):
    """A manager's or employee's calendar: their tasks and the content plan behind them."""

    tasks: list[StaffCalendarTask]
    entries: list[CalendarEntryResponse]
