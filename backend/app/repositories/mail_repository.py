"""Internal mailbox (owner request 2026-11-15): mail_messages, mail_recipients, mail_attachments."""

from __future__ import annotations

import builtins
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from app.database.connectivity import database_pool


@dataclass(frozen=True)
class MailRow:
    id: UUID
    thread_id: UUID
    reply_to_id: UUID | None
    kind: str
    subject: str
    body: str
    link: str
    created_at: datetime
    sender_id: UUID | None
    sender_name: str | None
    sender_role: str | None
    sender_image: str | None
    read_at: datetime | None  # for the person reading; None when they sent it
    recipients: list[tuple[UUID, str]]  # (id, name)
    attachments: int


@dataclass(frozen=True)
class MailFileRow:
    id: UUID
    message_id: UUID
    file_name: str
    storage_path: str
    mime_type: str
    size_bytes: int


_SELECT = """
    SELECT m.id, m.thread_id, m.reply_to_id, m.kind, m.subject, m.body, m.link, m.created_at,
      m.sender_id, su.name, sr.code, su.profile_image_url,
      (SELECT r.read_at FROM mail_recipients r WHERE r.message_id = m.id AND r.user_id = %(me)s),
      COALESCE((
        SELECT json_agg(json_build_array(u.id, u.name) ORDER BY u.name)
        FROM mail_recipients r JOIN users u ON u.id = r.user_id WHERE r.message_id = m.id
      ), '[]'::json),
      (SELECT COUNT(*) FROM mail_attachments a WHERE a.message_id = m.id)::int
    FROM mail_messages m
    LEFT JOIN users su ON su.id = m.sender_id
    LEFT JOIN roles sr ON sr.id = su.role_id
"""

# Mail this person can see: sent to them (not deleted by them) or sent by them (not deleted).
_VISIBLE = """
    m.company_id = %(company)s AND (
      EXISTS (SELECT 1 FROM mail_recipients r WHERE r.message_id = m.id AND r.user_id = %(me)s
              AND r.deleted_at IS NULL)
      OR (m.sender_id = %(me)s AND m.sender_deleted_at IS NULL)
    )
"""


def _row(values: tuple) -> MailRow:  # type: ignore[type-arg]
    data = list(values)
    data[13] = [(UUID(str(item[0])), str(item[1])) for item in (data[13] or [])]
    return MailRow(*data)


class MailRepository:
    def create(
        self,
        company_id: UUID,
        sender_id: UUID | None,
        recipients: list[UUID],
        subject: str,
        body: str,
        kind: str = "PERSONAL",
        link: str = "",
        reply_to: UUID | None = None,
        thread_id: UUID | None = None,
        files: list[tuple[str, str, str, int]] | None = None,
    ) -> UUID:
        message_id = uuid4()
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO mail_messages (id, company_id, sender_id, thread_id, reply_to_id, kind, "
                "subject, body, link, created_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s, "
                "NOW() AT TIME ZONE 'UTC')",
                (
                    message_id,
                    company_id,
                    sender_id,
                    thread_id or message_id,
                    reply_to,
                    kind,
                    subject,
                    body,
                    link,
                ),
            )
            for user_id in dict.fromkeys(recipients):
                cursor.execute(
                    "INSERT INTO mail_recipients (id, message_id, user_id, created_at) "
                    "VALUES (%s,%s,%s, NOW() AT TIME ZONE 'UTC')",
                    (uuid4(), message_id, user_id),
                )
            for name, path, mime, size in files or []:
                cursor.execute(
                    "INSERT INTO mail_attachments (id, message_id, file_name, storage_path, "
                    "mime_type, size_bytes, created_at) VALUES (%s,%s,%s,%s,%s,%s, "
                    "NOW() AT TIME ZONE 'UTC')",
                    (uuid4(), message_id, name, path, mime, size),
                )
        return message_id

    def list(
        self,
        company_id: UUID,
        me: UUID,
        folder: str,
        search: str,
        page: int,
        size: int,
    ) -> tuple[list[MailRow], int]:
        """Newest first. folder: INBOX (to me, from people), SYSTEM (from the app), SENT, ALL."""
        where = _VISIBLE
        if folder == "INBOX":
            where += " AND m.sender_id IS NOT NULL AND m.sender_id <> %(me)s"
        elif folder == "SYSTEM":
            where += " AND m.sender_id IS NULL"
        elif folder == "SENT":
            where += " AND m.sender_id = %(me)s"
        if search:
            where += (
                " AND (m.subject ILIKE %(term)s OR m.body ILIKE %(term)s OR su.name ILIKE %(term)s)"
            )
        params = {
            "company": company_id,
            "me": me,
            "term": f"%{search}%",
            "limit": size,
            "offset": (page - 1) * size,
        }
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM mail_messages m LEFT JOIN users su ON su.id = m.sender_id "
                f"WHERE {where}",
                params,
            )
            row = cursor.fetchone()
            total = int(row[0]) if row else 0
            cursor.execute(
                _SELECT + f" WHERE {where} ORDER BY m.created_at DESC LIMIT %(limit)s "
                "OFFSET %(offset)s",
                params,
            )
            return [_row(item) for item in cursor.fetchall()], total

    def thread(self, company_id: UUID, me: UUID, thread_id: UUID) -> builtins.list[MailRow]:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                _SELECT + f" WHERE {_VISIBLE} AND m.thread_id = %(thread)s ORDER BY m.created_at",
                {"company": company_id, "me": me, "thread": thread_id},
            )
            return [_row(item) for item in cursor.fetchall()]

    def get(self, company_id: UUID, me: UUID, message_id: UUID) -> MailRow | None:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                _SELECT + f" WHERE {_VISIBLE} AND m.id = %(id)s",
                {"company": company_id, "me": me, "id": message_id},
            )
            row = cursor.fetchone()
            return _row(row) if row else None

    def mark_thread_read(self, me: UUID, thread_id: UUID) -> int:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "UPDATE mail_recipients r SET read_at = NOW() AT TIME ZONE 'UTC' "
                "FROM mail_messages m WHERE m.id = r.message_id AND m.thread_id = %s "
                "AND r.user_id = %s AND r.read_at IS NULL",
                (thread_id, me),
            )
            return cursor.rowcount

    def hide(self, me: UUID, message_id: UUID) -> None:
        """Remove a mail from my own mailbox (others keep theirs)."""
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "UPDATE mail_recipients SET deleted_at = NOW() AT TIME ZONE 'UTC' "
                "WHERE message_id = %s AND user_id = %s",
                (message_id, me),
            )
            cursor.execute(
                "UPDATE mail_messages SET sender_deleted_at = NOW() AT TIME ZONE 'UTC' "
                "WHERE id = %s AND sender_id = %s",
                (message_id, me),
            )

    def unread(self, company_id: UUID, me: UUID) -> dict[str, int]:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FILTER (WHERE m.sender_id IS NOT NULL), "
                "COUNT(*) FILTER (WHERE m.sender_id IS NULL) "
                "FROM mail_recipients r JOIN mail_messages m ON m.id = r.message_id "
                "WHERE m.company_id = %s AND r.user_id = %s AND r.read_at IS NULL "
                "AND r.deleted_at IS NULL",
                (company_id, me),
            )
            row = cursor.fetchone()
            return (
                {"INBOX": int(row[0]), "SYSTEM": int(row[1])} if row else {"INBOX": 0, "SYSTEM": 0}
            )

    def files(self, message_ids: builtins.list[UUID]) -> builtins.list[MailFileRow]:
        if not message_ids:
            return []
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, message_id, file_name, storage_path, mime_type, size_bytes "
                "FROM mail_attachments WHERE message_id = ANY(%s) ORDER BY created_at",
                (message_ids,),
            )
            return [MailFileRow(*row) for row in cursor.fetchall()]

    def file(self, attachment_id: UUID) -> MailFileRow | None:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, message_id, file_name, storage_path, mime_type, size_bytes "
                "FROM mail_attachments WHERE id = %s",
                (attachment_id,),
            )
            row = cursor.fetchone()
            return MailFileRow(*row) if row else None
