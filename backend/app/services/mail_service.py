"""Internal mailbox (owner requests 2026-11-15).

People in the company write to each other here instead of email: managers, employees and the
admin with anyone on the team; clients only with the admins (and only the admins write to
clients). The app also writes here itself (sender None, shown as "Adverse") about tasks,
payments and meetings. The same system mail to the same person about the same thing is not
repeated within MAIL_REPEAT_WINDOW_MINUTES (e.g. a task submitted, sent back, submitted again).

Mail v2 works like Gmail: conversations, To/Cc/Bcc, star, archive, trash, drafts, schedule
send, forward with files, and tickets: anyone raises a problem from mail; it goes to the admins,
who assign it and move it through Open, In progress and Closed. The conversation is the thread.
"""

from __future__ import annotations

import builtins
import logging
import re
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import UploadFile

from app.core.settings import settings
from app.repositories.chat_repository import ChatRepository
from app.repositories.mail_repository import MailFileRow, MailRepository, MailRow, TicketRow
from app.schemas.agenda import AgendaEvent
from app.schemas.authentication import AuthContext
from app.schemas.mail import (
    MailAction,
    MailActionResponse,
    MailCard,
    MailConversation,
    MailDraftResponse,
    MailFile,
    MailFolder,
    MailItem,
    MailListResponse,
    MailPeopleResponse,
    MailPerson,
    MailThreadResponse,
    MailTicket,
    MailTicketListResponse,
    MailTicketUpdate,
    MailUnread,
)
from app.services import realtime
from app.services.authentication_service import AuthenticationError
from app.services.notification_service import notification_service
from app.services.task_file_storage import TaskFileStorage

logger = logging.getLogger(__name__)

ROLES = {
    "COMPANY_ADMIN": "ADMIN",
    "COMPANY_MANAGER": "MANAGER",
    "COMPANY_EMPLOYEE": "EMPLOYEE",
    "COMPANY_CLIENT": "CLIENT",
}
STAFF = ("COMPANY_ADMIN", "COMPANY_MANAGER", "COMPANY_EMPLOYEE")
MAX_MAIL_FILE_BYTES = 25 * 1024 * 1024
MAX_MAIL_FILES = 10
MAX_RECIPIENTS = 50
STATUS_LABEL = {"OPEN": "Open", "IN_PROGRESS": "In progress", "CLOSED": "Closed"}
PRIORITY_LABEL = {"LOW": "Low", "NORMAL": "Normal", "HIGH": "High", "URGENT": "Urgent"}


def _preview(body: str) -> str:
    text = " ".join(body.split())
    return text if len(text) <= 140 else f"{text[:140]}…"


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def ticket_code(number: int) -> str:
    return f"TKT-{number:04d}"


class MailService:
    def __init__(
        self,
        repository: MailRepository | None = None,
        people: ChatRepository | None = None,
        storage: TaskFileStorage | None = None,
    ) -> None:
        self.repository = repository or MailRepository()
        self.people_repository = people or ChatRepository()
        self.storage = storage or TaskFileStorage(
            Path("private-storage/mail-files"), MAX_MAIL_FILE_BYTES
        )

    # -- who --------------------------------------------------------------------------------

    @staticmethod
    def _me(context: AuthContext) -> tuple[UUID, str]:
        role = ROLES.get(context.role)
        if role is None or context.company_id is None:
            raise AuthenticationError(403, "MAIL_NOT_AVAILABLE", "Mail is not available here.")
        return context.company_id, role

    def _allowed(self, company_id: UUID, role: str, me: UUID) -> list[MailPerson]:
        if role == "CLIENT":
            codes: tuple[str, ...] = ("COMPANY_ADMIN",)
        elif role == "ADMIN":
            codes = (*STAFF, "COMPANY_CLIENT")
        else:
            codes = STAFF
        return [
            MailPerson(
                id=row.id,
                name=row.name,
                role=ROLES.get(row.role, "EMPLOYEE"),
                image=row.image,
            )
            for row in self.people_repository.people(company_id, codes)
            if row.id != me
        ]

    def _admins(self, company_id: UUID) -> list[UUID]:
        return [row.id for row in self.people_repository.people(company_id, ("COMPANY_ADMIN",))]

    def people(self, context: AuthContext) -> MailPeopleResponse:
        company_id, role = self._me(context)
        return MailPeopleResponse(people=self._allowed(company_id, role, context.user_id))

    # -- shaping ----------------------------------------------------------------------------

    @staticmethod
    def _person(user_id: UUID | None, name: str | None, role_code: str | None) -> MailPerson | None:
        if user_id is None:
            return None
        return MailPerson(
            id=user_id, name=name or "Someone", role=ROLES.get(role_code or "", "EMPLOYEE")
        )

    def _items(self, rows: list[MailRow], me: UUID) -> list[MailItem]:
        files: dict[UUID, list[MailFileRow]] = {}
        for item in self.repository.files([row.id for row in rows if row.attachments]):
            files.setdefault(item.message_id, []).append(item)
        out = []
        for row in rows:
            mine = row.sender_id == me
            people: dict[str, list[MailPerson]] = {"TO": [], "CC": [], "BCC": []}
            for user_id, name, kind, role_code in row.recipients:
                # Bcc stays private: the sender sees all of them, a Bcc person only themselves.
                if kind == "BCC" and not mine and user_id != me:
                    continue
                people.setdefault(kind, []).append(
                    MailPerson(id=user_id, name=name, role=ROLES.get(role_code, "EMPLOYEE"))
                )
            out.append(
                MailItem(
                    id=row.id,
                    thread_id=row.thread_id,
                    reply_to_id=row.reply_to_id,
                    kind=row.kind,
                    subject=row.subject,
                    preview=_preview(row.body),
                    body=row.body,
                    card=MailCard.model_validate(row.card) if row.card else None,
                    link=row.link,
                    created_at=row.created_at,
                    sender=(
                        MailPerson(
                            id=row.sender_id,
                            name=row.sender_name or "Someone",
                            role=ROLES.get(row.sender_role or "", "EMPLOYEE"),
                            image=row.sender_image,
                        )
                        if row.sender_id
                        else None
                    ),
                    recipients=people["TO"],
                    cc=people["CC"],
                    bcc=people["BCC"],
                    read=mine or row.read_at is not None,
                    mine=mine,
                    starred=row.starred,
                    trashed=row.trashed,
                    status=row.status,
                    scheduled_at=row.scheduled_at,
                    attachments=[
                        MailFile(
                            id=item.id,
                            file_name=item.file_name,
                            mime_type=item.mime_type,
                            size_bytes=item.size_bytes,
                        )
                        for item in files.get(row.id, [])
                    ],
                )
            )
        return out

    def _ticket(self, row: TicketRow, me: UUID, admin: bool) -> MailTicket:
        return MailTicket(
            id=row.id,
            number=row.number,
            code=ticket_code(row.number),
            thread_id=row.thread_id,
            message_id=row.first_message_id,
            subject=row.subject,
            priority=row.priority,
            status=row.status,
            raised_by=self._person(row.raised_by_id, row.raised_by_name, row.raised_by_role),
            assignee=self._person(row.assignee_id, row.assignee_name, row.assignee_role),
            created_at=row.created_at,
            updated_at=row.updated_at,
            closed_at=row.closed_at,
            last_at=row.last_at,
            count=row.count,
            can_manage=admin or row.assignee_id == me,
        )

    def _unread(self, company_id: UUID, me: UUID, role: str) -> MailUnread:
        counts = self.repository.counts(company_id, me)
        tickets = self.repository.ticket_counts(company_id, None if role == "ADMIN" else me)
        return MailUnread(
            inbox=counts["INBOX"],
            updates=counts["UPDATES"],
            system=counts["UPDATES"],
            total=counts["INBOX"] + counts["UPDATES"],
            drafts=counts["DRAFTS"],
            scheduled=counts["SCHEDULED"],
            tickets_open=tickets.get("OPEN", 0) + tickets.get("IN_PROGRESS", 0),
        )

    # -- reading ----------------------------------------------------------------------------

    def list(
        self, context: AuthContext, folder: MailFolder, search: str, page: int, size: int
    ) -> MailListResponse:
        company_id, role = self._me(context)
        me = context.user_id
        rows, stats, total = self.repository.threads(
            company_id, me, folder, search.strip()[:100], page, size
        )
        tickets = self.repository.ticket_for_threads(company_id, [row.thread_id for row in rows])
        items = []
        for row, shaped in zip(rows, self._items(rows, me), strict=True):
            stat = stats.get(row.thread_id)
            ticket = tickets.get(row.thread_id)
            items.append(
                MailConversation(
                    thread_id=row.thread_id,
                    message_id=row.id,
                    subject=row.subject,
                    preview=shaped.preview,
                    created_at=row.created_at,
                    sender=shaped.sender,
                    to=shaped.recipients + shaped.cc,
                    participants=stat.participants if stat else [],
                    count=max(1, stat.count if stat else 1),
                    unread=bool(stat and stat.unread),
                    starred=bool(stat and stat.starred),
                    has_files=bool(stat and stat.files) or bool(row.attachments),
                    kind=row.kind,
                    status=shaped.status,
                    scheduled_at=row.scheduled_at,
                    mine=shaped.mine,
                    ticket=self._ticket(ticket, me, role == "ADMIN") if ticket else None,
                )
            )
        return MailListResponse(
            items=items,
            page=page,
            page_size=size,
            total=total,
            total_pages=max(1, (total + size - 1) // size),
            unread=self._unread(company_id, me, role),
        )

    def unread(self, context: AuthContext) -> MailUnread:
        company_id, role = self._me(context)
        return self._unread(company_id, context.user_id, role)

    def thread(
        self, context: AuthContext, message_id: UUID, trash: bool = False
    ) -> MailThreadResponse:
        company_id, role = self._me(context)
        me = context.user_id
        first = self.repository.get(company_id, me, message_id)
        if first is None:
            raise AuthenticationError(404, "MAIL_NOT_FOUND", "That mail was not found.")
        if first.status == "DRAFT":
            return MailThreadResponse(
                thread_id=first.thread_id, subject=first.subject, items=self._items([first], me)
            )
        rows = self.repository.thread(company_id, me, first.thread_id, trash or first.trashed)
        if self.repository.mark_thread_read(me, first.thread_id):
            realtime.publish([me], "mail.read", {"thread_id": str(first.thread_id)})
        ticket = self.repository.ticket_for_threads(company_id, [first.thread_id]).get(
            first.thread_id
        )
        return MailThreadResponse(
            thread_id=first.thread_id,
            subject=rows[0].subject if rows else first.subject,
            items=self._items(rows, me),
            ticket=self._ticket(ticket, me, role == "ADMIN") if ticket else None,
            event=self._event(context, first.thread_id),
        )

    @staticmethod
    def _event(context: AuthContext, thread_id: UUID) -> AgendaEvent | None:
        """The meeting planned from this conversation; a calendar problem never blocks mail."""
        from app.services.agenda_service import agenda_service

        try:
            return agenda_service.event_for_thread(context, thread_id)
        except Exception:  # noqa: BLE001
            logger.warning("Calendar lookup for a mail failed", exc_info=True)
            return None

    def act(
        self, context: AuthContext, thread_ids: builtins.list[UUID], action: MailAction
    ) -> MailActionResponse:
        company_id, role = self._me(context)
        changed = self.repository.act(company_id, context.user_id, thread_ids, action)
        realtime.publish([context.user_id], "mail.read", {"action": action})
        return MailActionResponse(
            changed=changed, unread=self._unread(company_id, context.user_id, role)
        )

    def hide(self, context: AuthContext, message_id: UUID) -> None:
        company_id, _ = self._me(context)
        if self.repository.get(company_id, context.user_id, message_id) is None:
            raise AuthenticationError(404, "MAIL_NOT_FOUND", "That mail was not found.")
        self.repository.hide(context.user_id, message_id)
        realtime.publish([context.user_id], "mail.read", {"message_id": str(message_id)})

    def attachment(self, context: AuthContext, attachment_id: UUID) -> tuple[Path, str, str]:
        company_id, _ = self._me(context)
        found = self.repository.file(attachment_id)
        if (
            found is None
            or self.repository.get(company_id, context.user_id, found.message_id) is None
        ):
            raise AuthenticationError(404, "FILE_NOT_FOUND", "File not found.")
        return self.storage.path_for(found.storage_path), found.file_name, found.mime_type

    # -- writing ----------------------------------------------------------------------------

    def _recipients(
        self,
        company_id: UUID,
        role: str,
        me: UUID,
        to: builtins.list[UUID],
        cc: builtins.list[UUID],
        bcc: builtins.list[UUID],
        required: bool = True,
    ) -> builtins.list[tuple[UUID, str]]:
        pairs: builtins.list[tuple[UUID, str]] = []
        seen: set[UUID] = set()
        for kind, people in (("TO", to), ("CC", cc), ("BCC", bcc)):
            for user_id in people:
                if user_id not in seen and user_id != me:
                    seen.add(user_id)
                    pairs.append((user_id, kind))
        if required and not pairs:
            raise AuthenticationError(422, "NO_RECIPIENTS", "Choose who the mail is for.")
        if len(pairs) > MAX_RECIPIENTS:
            raise AuthenticationError(
                422, "TOO_MANY_RECIPIENTS", f"Send to at most {MAX_RECIPIENTS} people at once."
            )
        allowed = {person.id for person in self._allowed(company_id, role, me)}
        if any(user_id not in allowed for user_id, _ in pairs):
            raise AuthenticationError(
                403,
                "RECIPIENT_NOT_ALLOWED",
                "Clients can only write to the admin, and only the admin writes to clients.",
            )
        return pairs

    @staticmethod
    def _when(scheduled_at: datetime | None) -> datetime | None:
        if scheduled_at is None:
            return None
        moment = (
            scheduled_at.astimezone(UTC).replace(tzinfo=None)
            if scheduled_at.tzinfo
            else scheduled_at
        )
        now = _now()
        if moment < now + timedelta(seconds=30):
            raise AuthenticationError(422, "SCHEDULE_IN_PAST", "Pick a time in the future.")
        if moment > now + timedelta(days=366):
            raise AuthenticationError(422, "SCHEDULE_TOO_FAR", "Schedule at most a year ahead.")
        return moment

    def _store(
        self, company_id: UUID, me: UUID, uploads: builtins.list[UploadFile]
    ) -> builtins.list[tuple[str, str, str, int]]:
        uploads = [upload for upload in uploads if upload.filename]
        if len(uploads) > MAX_MAIL_FILES:
            raise AuthenticationError(
                422, "TOO_MANY_FILES", f"Attach at most {MAX_MAIL_FILES} files."
            )
        stored: builtins.list[tuple[str, str, str, int]] = []
        try:
            for upload in uploads:
                saved = self.storage.save(company_id, me, upload)
                stored.append(
                    (saved.file_name, saved.storage_path, saved.mime_type, saved.size_bytes)
                )
        except Exception:
            for _, path, _, _ in stored:
                self.storage.delete(path)
            raise
        return stored

    def _thread_for(
        self, company_id: UUID, me: UUID, reply_to: UUID | None, subject: str
    ) -> tuple[UUID | None, str]:
        if reply_to is None:
            return None, subject
        original = self.repository.get(company_id, me, reply_to)
        if original is None or original.status == "DRAFT":
            raise AuthenticationError(404, "MAIL_NOT_FOUND", "That mail was not found.")
        if not subject:
            subject = (
                original.subject
                if original.subject.lower().startswith("re:")
                else f"Re: {original.subject}"
            )
        return original.thread_id, subject

    def send(
        self,
        context: AuthContext,
        to: builtins.list[UUID],
        subject: str,
        body: str,
        reply_to: UUID | None,
        uploads: builtins.list[UploadFile],
        cc: builtins.list[UUID] | None = None,
        bcc: builtins.list[UUID] | None = None,
        forward_of: UUID | None = None,
        draft_id: UUID | None = None,
        scheduled_at: datetime | None = None,
        ticket_priority: str | None = None,
    ) -> MailThreadResponse:
        company_id, role = self._me(context)
        me = context.user_id
        ticket = ticket_priority if ticket_priority in PRIORITY_LABEL else None
        if ticket and (reply_to or forward_of or scheduled_at):
            raise AuthenticationError(
                422, "TICKET_NEW_ONLY", "Raise a ticket as a new mail, sent now."
            )
        if ticket:
            # A ticket always reaches the admins (who can write to everyone).
            extra = [admin for admin in self._admins(company_id) if admin != me]
            cc = [*(cc or []), *[admin for admin in extra if admin not in to]]
        recipients = self._recipients(company_id, role, me, to, cc or [], bcc or [])
        subject, body = subject.strip(), body.strip()
        thread_id, subject = self._thread_for(company_id, me, reply_to, subject)
        if not subject:
            raise AuthenticationError(422, "EMPTY_SUBJECT", "Add a subject.")
        source = None
        if forward_of is not None:
            source = self.repository.get(company_id, me, forward_of)
            if source is None:
                raise AuthenticationError(404, "MAIL_NOT_FOUND", "That mail was not found.")
        if (
            not body
            and not any(u.filename for u in uploads)
            and not (source and source.attachments)
        ):
            raise AuthenticationError(422, "EMPTY_MAIL", "Write a message or attach a file.")
        when = self._when(scheduled_at)
        status = "SCHEDULED" if when else "SENT"
        if draft_id is not None:
            draft = self.repository.get(company_id, me, draft_id)
            if draft is None or draft.sender_id != me or draft.status not in ("DRAFT", "SCHEDULED"):
                raise AuthenticationError(404, "DRAFT_NOT_FOUND", "That draft was not found.")
        stored = self._store(company_id, me, uploads)
        if draft_id is not None:
            self.repository.update_draft(
                draft_id, me, recipients, subject[:200], body[:20000], reply_to, thread_id
            )
            self.repository.unschedule(draft_id, me)
            self.repository.finish_draft(draft_id, me, status, when, stored)
            message_id = draft_id
        else:
            message_id = self.repository.create(
                company_id,
                me,
                recipients,
                subject[:200],
                body[:20000],
                kind="TICKET" if ticket else "PERSONAL",
                reply_to=reply_to,
                thread_id=thread_id,
                files=stored,
                status=status,
                scheduled_at=when,
            )
        if source is not None and source.attachments:
            self.repository.copy_files(source.id, message_id)
        if ticket:
            self.repository.create_ticket(company_id, message_id, subject[:200], ticket, me)
        if status == "SENT":
            self._deliver(company_id, me, [user for user, _ in recipients], message_id, subject)
        return self.thread(context, message_id)

    def _deliver(
        self,
        company_id: UUID,
        sender_id: UUID | None,
        recipients: builtins.list[UUID],
        message_id: UUID,
        subject: str,
    ) -> None:
        sender = self.people_repository.person(company_id, sender_id) if sender_id else None
        name = sender.name if sender else "Adverse"
        self._announce(company_id, recipients, message_id, f"Mail from {name}", subject, True)

    def save_draft(
        self,
        context: AuthContext,
        draft_id: UUID | None,
        to: builtins.list[UUID],
        cc: builtins.list[UUID],
        bcc: builtins.list[UUID],
        subject: str,
        body: str,
        reply_to: UUID | None,
    ) -> MailDraftResponse:
        company_id, role = self._me(context)
        me = context.user_id
        recipients = self._recipients(company_id, role, me, to, cc, bcc, required=False)
        thread_id, subject = self._thread_for(company_id, me, reply_to, subject.strip())
        if draft_id is None:
            draft_id = self.repository.create(
                company_id,
                me,
                recipients,
                subject[:200],
                body[:20000],
                reply_to=reply_to,
                thread_id=thread_id,
                status="DRAFT",
            )
        elif not self.repository.update_draft(
            draft_id, me, recipients, subject[:200], body[:20000], reply_to, thread_id
        ):
            raise AuthenticationError(404, "DRAFT_NOT_FOUND", "That draft was not found.")
        else:
            self.repository.unschedule(draft_id, me)
        realtime.publish([me], "mail.read", {"draft_id": str(draft_id)})
        return MailDraftResponse(id=draft_id, saved_at=_now())

    def discard_draft(self, context: AuthContext, draft_id: UUID) -> None:
        self._me(context)
        if not self.repository.discard_draft(draft_id, context.user_id):
            raise AuthenticationError(404, "DRAFT_NOT_FOUND", "That draft was not found.")
        realtime.publish([context.user_id], "mail.read", {"draft_id": str(draft_id)})

    def unschedule(self, context: AuthContext, message_id: UUID) -> MailDraftResponse:
        self._me(context)
        if not self.repository.unschedule(message_id, context.user_id):
            raise AuthenticationError(
                409, "NOT_SCHEDULED", "That mail is not waiting to be sent any more."
            )
        realtime.publish([context.user_id], "mail.read", {"draft_id": str(message_id)})
        return MailDraftResponse(id=message_id, saved_at=_now())

    def release_due(self) -> int:
        """Called by the scheduler: send scheduled mail whose time has come."""
        released = self.repository.release_due()
        for message_id, company_id, sender_id, subject in released:
            try:
                self._deliver(
                    company_id,
                    sender_id,
                    self.repository.recipients_of(message_id),
                    message_id,
                    subject,
                )
                if sender_id:
                    realtime.publish([sender_id], "mail.read", {"sent": str(message_id)})
            except Exception:  # noqa: BLE001
                logger.warning("Scheduled mail announce failed", exc_info=True)
        return len(released)

    # -- tickets ----------------------------------------------------------------------------

    def tickets(self, context: AuthContext, status: str | None) -> MailTicketListResponse:
        company_id, role = self._me(context)
        mine = None if role == "ADMIN" else context.user_id
        rows = self.repository.tickets(company_id, mine, status)
        counts = self.repository.ticket_counts(company_id, mine)
        return MailTicketListResponse(
            items=[self._ticket(row, context.user_id, role == "ADMIN") for row in rows],
            counts={key: counts.get(key, 0) for key in STATUS_LABEL},
        )

    def update_ticket(
        self, context: AuthContext, ticket_id: UUID, request: MailTicketUpdate
    ) -> MailTicket:
        company_id, role = self._me(context)
        me = context.user_id
        row = self.repository.ticket(company_id, ticket_id)
        if row is None:
            raise AuthenticationError(404, "TICKET_NOT_FOUND", "That ticket was not found.")
        admin = role == "ADMIN"
        if not admin and row.assignee_id != me:
            raise AuthenticationError(
                403, "TICKET_ADMIN_ONLY", "Only the admin or the person assigned can change it."
            )
        if not admin and (request.assignee_id or request.unassign or request.priority):
            raise AuthenticationError(
                403, "TICKET_ADMIN_ONLY", "Only the admin assigns a ticket or sets its priority."
            )
        changes: dict[str, object] = {}
        notes: builtins.list[str] = []
        actor = self.people_repository.person(company_id, me)
        actor_name = actor.name if actor else "Someone"
        if request.status and request.status != row.status:
            changes["status"] = request.status
            notes.append(f"{actor_name} changed the status to {STATUS_LABEL[request.status]}.")
        if request.priority and request.priority != row.priority:
            changes["priority"] = request.priority
            notes.append(f"Priority is now {PRIORITY_LABEL[request.priority]}.")
        new_assignee: UUID | None = None
        if request.unassign and row.assignee_id:
            changes["assignee_id"] = None
            notes.append(f"{actor_name} removed the assignee.")
        elif request.assignee_id and request.assignee_id != row.assignee_id:
            staff = {
                person.id: person for person in self.people_repository.people(company_id, STAFF)
            }
            person = staff.get(request.assignee_id)
            if person is None:
                raise AuthenticationError(
                    422, "ASSIGNEE_NOT_STAFF", "Assign the ticket to someone on the team."
                )
            changes["assignee_id"] = request.assignee_id
            new_assignee = request.assignee_id
            notes.append(f"Assigned to {person.name}.")
        if not changes:
            return self._ticket(row, me, admin)
        self.repository.update_ticket(ticket_id, changes)
        if new_assignee is not None:
            self.repository.add_to_thread(row.thread_id, new_assignee)
        updated = self.repository.ticket(company_id, ticket_id) or row
        people = [
            user
            for user in dict.fromkeys(
                [updated.raised_by_id, updated.assignee_id, *self._admins(company_id)]
            )
            if user and user != me
        ]
        if people and updated.first_message_id:
            # The change is written into the conversation, from the app, so everyone sees it.
            note_id = self.repository.create(
                company_id,
                None,
                people,
                f"Re: {updated.subject}"[:200],
                "\n".join(notes),
                kind="TICKET_UPDATE",
                reply_to=updated.first_message_id,
                thread_id=updated.thread_id,
            )
            self._announce(
                company_id,
                people,
                note_id,
                f"{ticket_code(updated.number)} updated",
                notes[0],
                notify=True,
            )
        return self._ticket(updated, me, admin)

    # -- the app's own mail -----------------------------------------------------------------

    def _announce(
        self,
        company_id: UUID,
        recipients: builtins.list[UUID],
        message_id: UUID,
        title: str,
        subject: str,
        notify: bool,
    ) -> None:
        realtime.publish(
            recipients,
            "mail.new",
            {"message_id": str(message_id), "subject": subject, "title": title},
        )
        if notify:
            notification_service.notify(
                company_id,
                recipients,
                "mail.new",
                title,
                subject,
                f"/mail?m={message_id}",
                {"message_id": str(message_id)},
            )

    def send_from(
        self,
        company_id: UUID,
        sender_id: UUID,
        recipients: Sequence[UUID],
        subject: str,
        body: str,
        link: str = "",
        kind: str = "PERSONAL",
    ) -> None:
        """A mail written for a person by the app (e.g. a calendar invitation from its
        organiser). Never raises."""
        try:
            people = [user_id for user_id in dict.fromkeys(recipients) if user_id != sender_id]
            if not people:
                return
            message_id = self.repository.create(
                company_id,
                sender_id,
                people,
                subject[:200],
                body[:20000],
                kind=kind[:40],
                link=link[:300],
            )
            self._deliver(company_id, sender_id, people, message_id, subject)
        except Exception:  # noqa: BLE001
            logger.warning("Mail failed: %s", subject, exc_info=True)

    def system(
        self,
        company_id: UUID,
        recipients: Sequence[UUID | None],
        subject: str,
        body: str,
        link: str = "",
        kind: str = "SYSTEM",
        once_key: str | None = None,
        notify: bool = False,
        once_seconds: int | None = None,
        *,
        card: dict[str, Any] | None = None,
        sender_id: UUID | None = None,
    ) -> None:
        """A mail from the app. Never raises: a failed mail must not undo the work.
        notify=False when the caller already sends its own bell notification.
        `sender_id`: the person whose action caused it (owner request 2026-11-19: a submitted task
        mails the admin from the employee, not from "Adverse"); they are never mailed themselves.
        `card`: the mail's layout, see `mail_card`."""
        try:
            people = [
                user_id for user_id in dict.fromkeys(recipients) if user_id and user_id != sender_id
            ]
            if once_key:
                people = [
                    user_id
                    for user_id in people
                    if self._first_time(f"{once_key}:{user_id}", once_seconds)
                ]
            if not people:
                return
            message_id = self.repository.create(
                company_id,
                sender_id,
                people,
                subject[:200],
                body[:20000],
                kind=kind[:40],
                link=link[:300],
                card=card or card_from_text(subject, body, kind, link),
            )
            sender = self.people_repository.person(company_id, sender_id) if sender_id else None
            title = f"Mail from {sender.name}" if sender else "New mail from Adverse"
            self._announce(company_id, people, message_id, title, subject, notify)
        except Exception:  # noqa: BLE001
            logger.warning("System mail failed: %s", subject, exc_info=True)

    @staticmethod
    def _first_time(key: str, seconds: int | None = None) -> bool:
        window = seconds if seconds is not None else settings.mail_repeat_window_minutes * 60
        if window <= 0:
            return True
        try:
            return bool(realtime._redis().set(f"mail:internal:{key}", "1", nx=True, ex=window))
        except Exception:  # noqa: BLE001 - without Redis, send rather than lose the mail
            return True


_HIGHLIGHT_LABELS = ("amount", "total", "balance", "amount due", "balance due", "advance left now")
_ROW = re.compile(r"^([A-Z][A-Za-z /&'().-]{1,28}):\s+(\S.{0,160})$")
KIND_LABELS = {
    "TASK": "Task update",
    "PAYMENT": "Payment",
    "INVOICE": "Invoice",
    "BUDGET": "Budget",
    "ADVANCE": "Advance",
    "CALENDAR": "Calendar",
    "MEETING": "Meeting",
    "TICKET": "Ticket",
    "WELCOME": "Welcome",
    "CALL": "Call",
    "SYSTEM": "Adverse",
}


def mail_card(
    title: str,
    lines: Sequence[str] = (),
    rows: Sequence[tuple[str, str]] = (),
    table: Sequence[Sequence[str]] = (),
    action: str | None = None,
    note: str | None = None,
    highlight: tuple[str, str] | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    """The layout of an app mail in the internal mailbox: a title, lines, detail rows, an item
    table (first row = headings), the button label for the mail's link and a small note. The
    first money row (Amount, Balance, ...) becomes the big highlight figure unless one is given
    (owner request 2026-11-19: mails must look advanced, not like plain text)."""
    pairs = [(label, value) for label, value in rows if value]
    if highlight is None:
        found = next((pair for pair in pairs if pair[0].strip().lower() in _HIGHLIGHT_LABELS), None)
        if found is not None:
            highlight = found
            pairs.remove(found)
    return {
        "title": title[:200],
        "lines": [line for line in lines if line][:12],
        "rows": [{"label": label, "value": value} for label, value in pairs][:16],
        "table": [[str(cell) for cell in row] for row in table][:200],
        "action": action,
        "note": note,
        "highlight": {"label": highlight[0], "value": highlight[1]} if highlight else None,
        "status": status,
    }


def card_from_text(subject: str, body: str, kind: str, link: str) -> dict[str, Any]:
    """A card for an app mail that was written as plain text: short "Label: value" lines become
    detail rows, the rest stay as lines, and a link gets a button."""
    lines: list[str] = []
    rows: list[tuple[str, str]] = []
    for line in body.splitlines():
        text = line.strip()
        if not text:
            continue
        match = _ROW.match(text)
        if match and len(rows) < 12:
            rows.append((match.group(1), match.group(2)))
        else:
            lines.append(text)
    action = None
    if link:
        action = {
            "TASK": "Open task",
            "PAYMENT": "Open payments",
            "INVOICE": "Open invoice",
            "BUDGET": "Open client",
            "CALENDAR": "Open calendar",
            "MEETING": "Open meeting",
            "TICKET": "Open ticket",
        }.get(kind, "Open in Adverse")
    return mail_card(subject, lines, rows, action=action)


mail_service = MailService()
