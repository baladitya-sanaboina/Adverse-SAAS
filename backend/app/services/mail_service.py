"""Internal mailbox inside Chat (owner request 2026-11-15).

People in the company write to each other here instead of email: managers, employees and the
admin with anyone on the team; clients only with the admins (and only the admins write to
clients). The app also writes here itself (sender None, shown as "Adverse") about tasks,
payments and meetings. The same system mail to the same person about the same thing is not
repeated within MAIL_REPEAT_WINDOW_MINUTES (e.g. a task submitted, sent back, submitted again).
"""

from __future__ import annotations

import builtins
import logging
from collections.abc import Sequence
from pathlib import Path
from uuid import UUID

from fastapi import UploadFile

from app.core.settings import settings
from app.repositories.chat_repository import ChatRepository
from app.repositories.mail_repository import MailFileRow, MailRepository, MailRow
from app.schemas.authentication import AuthContext
from app.schemas.mail import (
    MailFile,
    MailFolder,
    MailItem,
    MailListResponse,
    MailPeopleResponse,
    MailPerson,
    MailThreadResponse,
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


def _preview(body: str) -> str:
    text = " ".join(body.split())
    return text if len(text) <= 140 else f"{text[:140]}…"


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

    def people(self, context: AuthContext) -> MailPeopleResponse:
        company_id, role = self._me(context)
        return MailPeopleResponse(people=self._allowed(company_id, role, context.user_id))

    # -- shaping ----------------------------------------------------------------------------

    def _items(self, rows: list[MailRow], me: UUID) -> list[MailItem]:
        files: dict[UUID, list[MailFileRow]] = {}
        for item in self.repository.files([row.id for row in rows if row.attachments]):
            files.setdefault(item.message_id, []).append(item)
        return [
            MailItem(
                id=row.id,
                thread_id=row.thread_id,
                kind=row.kind,
                subject=row.subject,
                preview=_preview(row.body),
                body=row.body,
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
                recipients=[
                    MailPerson(id=user_id, name=name, role="EMPLOYEE")
                    for user_id, name in row.recipients
                ],
                read=row.sender_id == me or row.read_at is not None,
                mine=row.sender_id == me,
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
            for row in rows
        ]

    def _unread(self, company_id: UUID, me: UUID) -> MailUnread:
        counts = self.repository.unread(company_id, me)
        return MailUnread(
            inbox=counts["INBOX"], system=counts["SYSTEM"], total=counts["INBOX"] + counts["SYSTEM"]
        )

    # -- reading ----------------------------------------------------------------------------

    def list(
        self, context: AuthContext, folder: MailFolder, search: str, page: int, size: int
    ) -> MailListResponse:
        company_id, _ = self._me(context)
        rows, total = self.repository.list(
            company_id, context.user_id, folder, search.strip()[:100], page, size
        )
        return MailListResponse(
            items=self._items(rows, context.user_id),
            page=page,
            page_size=size,
            total=total,
            total_pages=max(1, (total + size - 1) // size),
            unread=self._unread(company_id, context.user_id),
        )

    def unread(self, context: AuthContext) -> MailUnread:
        company_id, _ = self._me(context)
        return self._unread(company_id, context.user_id)

    def thread(self, context: AuthContext, message_id: UUID) -> MailThreadResponse:
        company_id, _ = self._me(context)
        first = self.repository.get(company_id, context.user_id, message_id)
        if first is None:
            raise AuthenticationError(404, "MAIL_NOT_FOUND", "That mail was not found.")
        rows = self.repository.thread(company_id, context.user_id, first.thread_id)
        if self.repository.mark_thread_read(context.user_id, first.thread_id):
            realtime.publish([context.user_id], "mail.read", {"thread_id": str(first.thread_id)})
        return MailThreadResponse(
            thread_id=first.thread_id,
            subject=rows[0].subject if rows else first.subject,
            items=self._items(rows, context.user_id),
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

    def send(
        self,
        context: AuthContext,
        to: builtins.list[UUID],
        subject: str,
        body: str,
        reply_to: UUID | None,
        uploads: builtins.list[UploadFile],
    ) -> MailThreadResponse:
        company_id, role = self._me(context)
        allowed = {person.id: person for person in self._allowed(company_id, role, context.user_id)}
        recipients = list(dict.fromkeys(to))
        if not recipients:
            raise AuthenticationError(422, "NO_RECIPIENTS", "Choose who the mail is for.")
        if any(user_id not in allowed for user_id in recipients):
            raise AuthenticationError(
                403,
                "RECIPIENT_NOT_ALLOWED",
                "Clients can only write to the admin, and only the admin writes to clients.",
            )
        subject, body = subject.strip(), body.strip()
        thread_id: UUID | None = None
        if reply_to is not None:
            original = self.repository.get(company_id, context.user_id, reply_to)
            if original is None:
                raise AuthenticationError(404, "MAIL_NOT_FOUND", "That mail was not found.")
            thread_id = original.thread_id
            if not subject:
                subject = (
                    original.subject
                    if original.subject.lower().startswith("re:")
                    else f"Re: {original.subject}"
                )
        if not subject:
            raise AuthenticationError(422, "EMPTY_SUBJECT", "Add a subject.")
        uploads = [upload for upload in uploads if upload.filename]
        if not body and not uploads:
            raise AuthenticationError(422, "EMPTY_MAIL", "Write a message or attach a file.")
        if len(uploads) > MAX_MAIL_FILES:
            raise AuthenticationError(
                422, "TOO_MANY_FILES", f"Attach at most {MAX_MAIL_FILES} files."
            )
        stored = []
        try:
            for upload in uploads:
                saved = self.storage.save(company_id, context.user_id, upload)
                stored.append(
                    (saved.file_name, saved.storage_path, saved.mime_type, saved.size_bytes)
                )
        except Exception:
            for _, path, _, _ in stored:
                self.storage.delete(path)
            raise
        message_id = self.repository.create(
            company_id,
            context.user_id,
            recipients,
            subject[:200],
            body[:20000],
            reply_to=reply_to,
            thread_id=thread_id,
            files=stored,
        )
        sender = self.people_repository.person(company_id, context.user_id)
        name = sender.name if sender else "Someone"
        self._announce(
            company_id, recipients, message_id, f"Mail from {name}", subject, notify=True
        )
        return self.thread(context, message_id)

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
                f"/chat?mail={message_id}",
                {"message_id": str(message_id)},
            )

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
    ) -> None:
        """A mail from the app itself. Never raises: a failed mail must not undo the work.
        notify=False when the caller already sends its own bell notification."""
        try:
            people = [user_id for user_id in dict.fromkeys(recipients) if user_id]
            if once_key:
                people = [
                    user_id for user_id in people if self._first_time(f"{once_key}:{user_id}")
                ]
            if not people:
                return
            message_id = self.repository.create(
                company_id,
                None,
                people,
                subject[:200],
                body[:20000],
                kind=kind[:40],
                link=link[:300],
            )
            self._announce(company_id, people, message_id, "New mail from Adverse", subject, notify)
        except Exception:  # noqa: BLE001
            logger.warning("System mail failed: %s", subject, exc_info=True)

    @staticmethod
    def _first_time(key: str, seconds: int | None = None) -> bool:
        window = seconds if seconds is not None else settings.mail_repeat_window_minutes * 60
        if window <= 0:
            return True
        try:
            return bool(
                realtime._redis().set(
                    f"mail:internal:{key}",
                    "1",
                    nx=True,
                    ex=settings.mail_repeat_window_minutes * 60,
                )
            )
        except Exception:  # noqa: BLE001 - without Redis, send rather than lose the mail
            return True


mail_service = MailService()
