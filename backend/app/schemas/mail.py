"""Internal mailbox shapes (owner request 2026-11-15)."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

MailFolder = Literal["INBOX", "SYSTEM", "SENT", "ALL"]
MailRole = Literal["ADMIN", "MANAGER", "EMPLOYEE", "CLIENT"]


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
    kind: str
    subject: str
    preview: str
    body: str
    link: str
    created_at: datetime
    sender: MailPerson | None  # None: sent by the app itself
    recipients: list[MailPerson]
    read: bool
    mine: bool
    attachments: list[MailFile]


class MailUnread(BaseModel):
    inbox: int
    system: int
    total: int


class MailListResponse(BaseModel):
    items: list[MailItem]
    page: int
    page_size: int
    total: int
    total_pages: int
    unread: MailUnread


class MailThreadResponse(BaseModel):
    thread_id: UUID
    subject: str
    items: list[MailItem]


class MailPeopleResponse(BaseModel):
    people: list[MailPerson]
