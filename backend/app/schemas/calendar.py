"""Content calendar shapes (Phase 13)."""

from datetime import date, datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.production import NamedRef
from app.services.production_rules import TaskStatus


def _strip(value: str) -> str:
    return value.strip()


def _check_url(value: str) -> str:
    value = value.strip()
    if value and not value.lower().startswith(("http://", "https://")):
        raise ValueError("The reference link must start with http:// or https://.")
    return value


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
    created_by_name: str
    created_at: datetime
    updated_at: datetime


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

    _strip_text = field_validator("title", "notes")(_strip)
    _url = field_validator("reference_url", "script_url", "pdf_url")(_check_url)

    @model_validator(mode="after")
    def check_title(self) -> Self:
        if not self.title:
            raise ValueError("Title cannot be blank.")
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
