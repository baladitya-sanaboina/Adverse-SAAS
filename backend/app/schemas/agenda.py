"""Calendar shapes (owner request 2026-11-15)."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

AgendaRole = Literal["ADMIN", "MANAGER", "EMPLOYEE"]
Response = Literal["PENDING", "YES", "NO", "MAYBE"]
Colour = Literal["blue", "green", "red", "purple", "amber", "teal", "pink", "grey"]
Scope = Literal["mine", "team", "all"]
TodoPriority = Literal["LOW", "NORMAL", "HIGH"]


class AgendaPerson(BaseModel):
    id: UUID
    name: str
    role: str
    image: str | None = None


class AgendaAttendee(BaseModel):
    person: AgendaPerson
    response: Response


class AgendaEvent(BaseModel):
    id: UUID
    title: str
    notes: str
    location: str
    starts_at: datetime
    ends_at: datetime
    all_day: bool
    colour: str
    video: bool
    conversation_id: UUID | None
    mail_thread_id: UUID | None
    owner: AgendaPerson
    attendees: list[AgendaAttendee]
    my_response: Response | None  # None: I am not invited (owner, or seen as admin/manager)
    can_edit: bool


class AgendaTodo(BaseModel):
    id: UUID
    title: str
    notes: str
    due_date: date | None
    due_at: datetime | None
    priority: TodoPriority
    done: bool
    owner: AgendaPerson
    mine: bool


class AgendaTaskDue(BaseModel):
    id: UUID
    code: str
    title: str
    due_date: date
    status: str
    assignee: str | None
    client: str | None


class AgendaMeeting(BaseModel):
    id: UUID
    conversation_id: UUID
    title: str
    starts_at: datetime
    ends_at: datetime
    kind: str
    room: str


class AgendaFeed(BaseModel):
    events: list[AgendaEvent]
    meetings: list[AgendaMeeting]
    tasks: list[AgendaTaskDue]
    todos: list[AgendaTodo]
    people: list[AgendaPerson]  # who I can see and invite
    scope: Scope
    role: AgendaRole


class EventRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=160)
    notes: str = Field(default="", max_length=2000)
    location: str = Field(default="", max_length=200)
    starts_at: datetime
    ends_at: datetime
    all_day: bool = False
    colour: Colour = "blue"
    video: bool = False
    attendee_ids: list[UUID] = Field(default_factory=list, max_length=50)
    mail_thread_id: UUID | None = None
    invite: bool = True  # False when the invitation already went as a mail

    @field_validator("title", "location")
    @classmethod
    def strip(cls, value: str) -> str:
        return value.strip()


class EventUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=160)
    notes: str | None = Field(default=None, max_length=2000)
    location: str | None = Field(default=None, max_length=200)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    all_day: bool | None = None
    colour: Colour | None = None
    attendee_ids: list[UUID] | None = Field(default=None, max_length=50)


class RespondRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    response: Literal["YES", "NO", "MAYBE"]


class TodoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    notes: str = Field(default="", max_length=2000)
    due_date: date | None = None
    due_at: datetime | None = None  # with a time: alerts 10 minutes before and at the time
    priority: TodoPriority = "NORMAL"

    @field_validator("title")
    @classmethod
    def strip(cls, value: str) -> str:
        return value.strip()


class TodoUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    notes: str | None = Field(default=None, max_length=2000)
    due_date: date | None = None
    due_at: datetime | None = None
    clear_due: bool = False
    priority: TodoPriority | None = None
    done: bool | None = None
