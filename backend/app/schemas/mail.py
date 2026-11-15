"""Internal mailbox shapes (owner requests 2026-11-15; mail v2: Gmail-style)."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

MailFolder = Literal["INBOX", "UPDATES", "STARRED", "SENT", "SCHEDULED", "DRAFTS", "ALL", "TRASH"]
MailRole = Literal["ADMIN", "MANAGER", "EMPLOYEE", "CLIENT"]
MailAction = Literal[
    "archive", "inbox", "trash", "restore", "purge", "star", "unstar", "read", "unread"
]
TicketStatus = Literal["OPEN", "IN_PROGRESS", "CLOSED"]
TicketPriority = Literal["LOW", "NORMAL", "HIGH", "URGENT"]


class MailPerson(BaseModel):
    id: UUID
    name: str
    role: MailRole
    image: str | None = None


class MailFile(BaseModel):
    id: UUID
    file_name: str
    mime_type: str
    size_bytes: int


class MailItem(BaseModel):
    id: UUID
    thread_id: UUID
    reply_to_id: UUID | None = None
    kind: str
    subject: str
    preview: str
    body: str
    link: str
    created_at: datetime
    sender: MailPerson | None  # None: sent by the app itself
    recipients: list[MailPerson]  # To
    cc: list[MailPerson] = []
    bcc: list[MailPerson] = []  # only the sender (and each Bcc person, themselves) sees these
    read: bool
    mine: bool
    starred: bool = False
    trashed: bool = False
    status: Literal["SENT", "SCHEDULED", "DRAFT"] = "SENT"
    scheduled_at: datetime | None = None
    attachments: list[MailFile]


class MailTicket(BaseModel):
    id: UUID
    number: int
    code: str  # TKT-0001
    thread_id: UUID
    message_id: UUID | None
    subject: str
    priority: TicketPriority
    status: TicketStatus
    raised_by: MailPerson | None
    assignee: MailPerson | None
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None
    last_at: datetime | None
    count: int
    can_manage: bool


class MailConversation(BaseModel):
    """A row in a folder: one conversation, shown by its newest message there."""

    thread_id: UUID
    message_id: UUID
    subject: str
    preview: str
    created_at: datetime
    sender: MailPerson | None
    to: list[MailPerson]
    participants: list[str]
    count: int
    unread: bool
    starred: bool
    has_files: bool
    kind: str
    status: Literal["SENT", "SCHEDULED", "DRAFT"]
    scheduled_at: datetime | None
    mine: bool
    ticket: MailTicket | None = None


class MailUnread(BaseModel):
    inbox: int
    updates: int
    total: int  # the red badge: unread conversations in Inbox and Updates
    drafts: int = 0
    scheduled: int = 0
    tickets_open: int = 0
    # Older clients read these names.
    system: int = 0


class MailListResponse(BaseModel):
    items: list[MailConversation]
    page: int
    page_size: int
    total: int
    total_pages: int
    unread: MailUnread


class MailThreadResponse(BaseModel):
    thread_id: UUID
    subject: str
    items: list[MailItem]
    ticket: MailTicket | None = None


class MailPeopleResponse(BaseModel):
    people: list[MailPerson]


class MailActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    thread_ids: list[UUID] = Field(min_length=1, max_length=100)
    action: MailAction


class MailActionResponse(BaseModel):
    changed: int
    unread: MailUnread


class MailDraftResponse(BaseModel):
    id: UUID
    saved_at: datetime


class MailTicketListResponse(BaseModel):
    items: list[MailTicket]
    counts: dict[str, int]


class MailTicketUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: TicketStatus | None = None
    priority: TicketPriority | None = None
    assignee_id: UUID | None = None
    unassign: bool = False
