"""Internal mailbox (owner requests 2026-11-15): mail_messages, mail_recipients, mail_attachments,
mail_tickets. Mail v2 works like Gmail: conversations (threads), To/Cc/Bcc, star, archive, trash,
delete forever, drafts, schedule send, and tickets raised from mail."""

from __future__ import annotations

import builtins
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from app.database.connectivity import database_pool

FOLDERS = ("INBOX", "UPDATES", "STARRED", "SENT", "SCHEDULED", "DRAFTS", "ALL", "TRASH")
ACTIONS = ("archive", "inbox", "trash", "restore", "purge", "star", "unstar", "read", "unread")


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
    recipients: list[tuple[UUID, str, str, str]]  # (id, name, TO|CC|BCC, role code)
    attachments: int
    status: str = "SENT"
    scheduled_at: datetime | None = None
    starred: bool = False
    trashed: bool = False
    card: dict[str, Any] | None = None


@dataclass(frozen=True)
class MailFileRow:
    id: UUID
    message_id: UUID
    file_name: str
    storage_path: str
    mime_type: str
    size_bytes: int


@dataclass(frozen=True)
class ThreadStats:
    count: int
    unread: bool
    starred: bool
    files: bool
    participants: list[str]


@dataclass(frozen=True)
class TicketRow:
    id: UUID
    number: int
    thread_id: UUID
    subject: str
    priority: str
    status: str
    raised_by_id: UUID | None
    raised_by_name: str | None
    raised_by_role: str | None
    assignee_id: UUID | None
    assignee_name: str | None
    assignee_role: str | None
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None
    first_message_id: UUID | None
    last_at: datetime | None
    count: int


# My recipient row on message m (not deleted forever), with an optional extra condition.
def _mine_as_recipient(extra: str = "") -> str:
    return (
        "EXISTS (SELECT 1 FROM mail_recipients r WHERE r.message_id = m.id "
        f"AND r.user_id = %(me)s AND r.purged_at IS NULL {extra})"
    )


_MINE = "(m.sender_id = %(me)s AND m.sender_purged_at IS NULL)"
_RECEIVED = f"(m.status = 'SENT' AND {_mine_as_recipient('AND r.deleted_at IS NULL')})"
_IN_BOX = _mine_as_recipient("AND r.deleted_at IS NULL AND r.archived_at IS NULL")

# Which of my messages a folder lists (its threads are listed, newest activity first).
FOLDER_SQL = {
    "INBOX": (
        "(m.status = 'SENT' AND m.sender_id IS NOT NULL AND m.sender_id <> %(me)s "
        f"AND {_IN_BOX})"
    ),
    "UPDATES": f"(m.status = 'SENT' AND m.sender_id IS NULL AND {_IN_BOX})",
    "STARRED": (
        "((m.status = 'SENT' AND "
        f"{_mine_as_recipient('AND r.deleted_at IS NULL AND r.starred_at IS NOT NULL')}) "
        f"OR ({_MINE} AND m.sender_deleted_at IS NULL AND m.sender_starred_at IS NOT NULL))"
    ),
    "SENT": f"({_MINE} AND m.status = 'SENT' AND m.sender_deleted_at IS NULL)",
    "SCHEDULED": f"({_MINE} AND m.status = 'SCHEDULED' AND m.sender_deleted_at IS NULL)",
    "DRAFTS": f"({_MINE} AND m.status = 'DRAFT' AND m.sender_deleted_at IS NULL)",
    "ALL": f"({_RECEIVED} OR ({_MINE} AND m.status = 'SENT' AND m.sender_deleted_at IS NULL))",
    "TRASH": (
        f"((m.status = 'SENT' AND {_mine_as_recipient('AND r.deleted_at IS NOT NULL')}) "
        f"OR ({_MINE} AND m.sender_deleted_at IS NOT NULL))"
    ),
}
# What a conversation shows when opened (my scheduled replies included; drafts open in compose).
_SHOWN = (
    f"({_RECEIVED} OR ({_MINE} AND m.sender_deleted_at IS NULL "
    "AND m.status IN ('SENT', 'SCHEDULED')))"
)
_SHOWN_IN_TRASH = FOLDER_SQL["TRASH"]

_SELECT = """
    SELECT m.id, m.thread_id, m.reply_to_id, m.kind, m.subject, m.body, m.link, m.created_at,
      m.sender_id, su.name, sr.code, su.profile_image_url,
      (SELECT r.read_at FROM mail_recipients r WHERE r.message_id = m.id AND r.user_id = %(me)s),
      COALESCE((
        SELECT json_agg(json_build_array(u.id, u.name, r.kind, ro.code) ORDER BY r.kind, u.name)
        FROM mail_recipients r JOIN users u ON u.id = r.user_id JOIN roles ro ON ro.id = u.role_id
        WHERE r.message_id = m.id
      ), '[]'::json),
      (SELECT COUNT(*) FROM mail_attachments a WHERE a.message_id = m.id)::int,
      m.status, m.scheduled_at,
      (EXISTS (SELECT 1 FROM mail_recipients r WHERE r.message_id = m.id AND r.user_id = %(me)s
               AND r.starred_at IS NOT NULL)
       OR (m.sender_id = %(me)s AND m.sender_starred_at IS NOT NULL)),
      (EXISTS (SELECT 1 FROM mail_recipients r WHERE r.message_id = m.id AND r.user_id = %(me)s
               AND r.deleted_at IS NOT NULL)
       OR (m.sender_id = %(me)s AND m.sender_deleted_at IS NOT NULL)),
      m.card
    FROM mail_messages m
    LEFT JOIN users su ON su.id = m.sender_id
    LEFT JOIN roles sr ON sr.id = su.role_id
"""

_TICKET = """
    SELECT t.id, t.number, t.thread_id, t.subject, t.priority, t.status,
      t.raised_by_id, ru.name, rr.code, t.assignee_id, au.name, ar.code,
      t.created_at, t.updated_at, t.closed_at,
      (SELECT m.id FROM mail_messages m WHERE m.thread_id = t.thread_id AND m.status = 'SENT'
       ORDER BY m.created_at LIMIT 1),
      (SELECT MAX(m.created_at) FROM mail_messages m WHERE m.thread_id = t.thread_id
       AND m.status = 'SENT'),
      (SELECT COUNT(*) FROM mail_messages m WHERE m.thread_id = t.thread_id
       AND m.status = 'SENT')::int
    FROM mail_tickets t
    LEFT JOIN users ru ON ru.id = t.raised_by_id LEFT JOIN roles rr ON rr.id = ru.role_id
    LEFT JOIN users au ON au.id = t.assignee_id LEFT JOIN roles ar ON ar.id = au.role_id
"""


def _row(values: tuple[Any, ...]) -> MailRow:
    data = list(values)
    data[13] = [
        (UUID(str(item[0])), str(item[1]), str(item[2]), str(item[3])) for item in (data[13] or [])
    ]
    return MailRow(*data)


def _insert_recipients(
    cursor: Any, message_id: UUID, recipients: builtins.list[tuple[UUID, str]]
) -> None:
    seen: set[UUID] = set()
    for user_id, kind in recipients:
        if user_id in seen:
            continue
        seen.add(user_id)
        cursor.execute(
            "INSERT INTO mail_recipients (id, message_id, user_id, kind, created_at) "
            "VALUES (%s,%s,%s,%s, NOW() AT TIME ZONE 'UTC')",
            (uuid4(), message_id, user_id, kind),
        )


def _insert_files(
    cursor: Any, message_id: UUID, files: builtins.list[tuple[str, str, str, int]]
) -> None:
    for name, path, mime, size in files:
        cursor.execute(
            "INSERT INTO mail_attachments (id, message_id, file_name, storage_path, "
            "mime_type, size_bytes, created_at) VALUES (%s,%s,%s,%s,%s,%s, "
            "NOW() AT TIME ZONE 'UTC')",
            (uuid4(), message_id, name, path, mime, size),
        )


class MailRepository:
    # -- writing ----------------------------------------------------------------------------

    def create(
        self,
        company_id: UUID,
        sender_id: UUID | None,
        recipients: builtins.list[UUID] | builtins.list[tuple[UUID, str]],
        subject: str,
        body: str,
        kind: str = "PERSONAL",
        link: str = "",
        reply_to: UUID | None = None,
        thread_id: UUID | None = None,
        files: builtins.list[tuple[str, str, str, int]] | None = None,
        status: str = "SENT",
        scheduled_at: datetime | None = None,
        card: dict[str, Any] | None = None,
        starred: bool = False,
    ) -> UUID:
        """recipients: user ids (all To) or (user id, TO|CC|BCC) pairs. `card` is the mail's
        structured layout (title, rows, table, button) for app mails. `starred`: already
        starred for the recipients (a priority mail)."""
        pairs = [item if isinstance(item, tuple) else (item, "TO") for item in recipients]
        message_id = uuid4()
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO mail_messages (id, company_id, sender_id, thread_id, reply_to_id, kind, "
                "subject, body, link, status, scheduled_at, card, created_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, NOW() AT TIME ZONE 'UTC')",
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
                    status,
                    scheduled_at,
                    Jsonb(card) if card else None,
                ),
            )
            _insert_recipients(cursor, message_id, pairs)
            _insert_files(cursor, message_id, files or [])
            if starred:
                cursor.execute(
                    "UPDATE mail_recipients SET starred_at = NOW() AT TIME ZONE 'UTC' "
                    "WHERE message_id = %s",
                    (message_id,),
                )
        return message_id

    def update_draft(
        self,
        message_id: UUID,
        sender_id: UUID,
        recipients: builtins.list[tuple[UUID, str]],
        subject: str,
        body: str,
        reply_to: UUID | None,
        thread_id: UUID | None,
    ) -> bool:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "UPDATE mail_messages SET subject=%s, body=%s, reply_to_id=%s, "
                "thread_id=COALESCE(%s, id), scheduled_at=NULL, created_at=NOW() AT TIME ZONE 'UTC' "
                "WHERE id=%s AND sender_id=%s AND status IN ('DRAFT', 'SCHEDULED') "
                "AND sender_purged_at IS NULL",
                (subject, body, reply_to, thread_id, message_id, sender_id),
            )
            if cursor.rowcount != 1:
                return False
            cursor.execute("DELETE FROM mail_recipients WHERE message_id=%s", (message_id,))
            _insert_recipients(cursor, message_id, recipients)
        return True

    def finish_draft(
        self,
        message_id: UUID,
        sender_id: UUID,
        status: str,
        scheduled_at: datetime | None,
        files: builtins.list[tuple[str, str, str, int]],
    ) -> bool:
        """A draft goes out now (SENT) or later (SCHEDULED)."""
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "UPDATE mail_messages SET status=%s, scheduled_at=%s, "
                "created_at=NOW() AT TIME ZONE 'UTC' WHERE id=%s AND sender_id=%s "
                "AND status = 'DRAFT' AND sender_purged_at IS NULL",
                (status, scheduled_at, message_id, sender_id),
            )
            if cursor.rowcount != 1:
                return False
            _insert_files(cursor, message_id, files)
        return True

    def unschedule(self, message_id: UUID, sender_id: UUID) -> bool:
        """Cancel a scheduled send: the mail goes back to Drafts."""
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "UPDATE mail_messages SET status='DRAFT', scheduled_at=NULL "
                "WHERE id=%s AND sender_id=%s AND status='SCHEDULED'",
                (message_id, sender_id),
            )
            return cursor.rowcount == 1

    def discard_draft(self, message_id: UUID, sender_id: UUID) -> bool:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "UPDATE mail_messages SET sender_purged_at=NOW() AT TIME ZONE 'UTC', "
                "sender_deleted_at=COALESCE(sender_deleted_at, NOW() AT TIME ZONE 'UTC') "
                "WHERE id=%s AND sender_id=%s AND status='DRAFT'",
                (message_id, sender_id),
            )
            return cursor.rowcount == 1

    def release_due(self) -> builtins.list[tuple[UUID, UUID, UUID | None, str]]:
        """Scheduled mail whose time has come is sent: (id, company, sender, subject)."""
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "UPDATE mail_messages SET status='SENT', created_at=NOW() AT TIME ZONE 'UTC' "
                "WHERE status='SCHEDULED' AND scheduled_at <= NOW() AT TIME ZONE 'UTC' "
                "AND sender_purged_at IS NULL "
                "RETURNING id, company_id, sender_id, subject"
            )
            return [(row[0], row[1], row[2], row[3]) for row in cursor.fetchall()]

    def copy_files(self, source_id: UUID, target_id: UUID) -> None:
        """Forwarding: the new mail points at the same stored files."""
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO mail_attachments (id, message_id, file_name, storage_path, "
                "mime_type, size_bytes, created_at) SELECT gen_random_uuid(), %s, file_name, "
                "storage_path, mime_type, size_bytes, NOW() AT TIME ZONE 'UTC' "
                "FROM mail_attachments WHERE message_id = %s",
                (target_id, source_id),
            )

    def recipients_of(self, message_id: UUID) -> builtins.list[UUID]:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute("SELECT user_id FROM mail_recipients WHERE message_id=%s", (message_id,))
            return [row[0] for row in cursor.fetchall()]

    # -- reading ----------------------------------------------------------------------------

    def threads(
        self,
        company_id: UUID,
        me: UUID,
        folder: str,
        search: str,
        page: int,
        size: int,
    ) -> tuple[builtins.list[MailRow], dict[UUID, ThreadStats], int]:
        """One row per conversation (its newest message in the folder), newest first."""
        where = f"m.company_id = %(company)s AND {FOLDER_SQL[folder]}"
        if search:
            where += (
                " AND (m.subject ILIKE %(term)s OR m.body ILIKE %(term)s "
                "OR COALESCE(su.name, 'Adverse') ILIKE %(term)s)"
            )
        params: dict[str, Any] = {
            "company": company_id,
            "me": me,
            "term": f"%{search}%",
            "limit": size,
            "offset": (page - 1) * size,
        }
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(DISTINCT m.thread_id) FROM mail_messages m "
                f"LEFT JOIN users su ON su.id = m.sender_id WHERE {where}",
                params,
            )
            row = cursor.fetchone()
            total = int(row[0]) if row else 0
            cursor.execute(
                "SELECT m.thread_id FROM mail_messages m LEFT JOIN users su ON su.id = m.sender_id "
                f"WHERE {where} GROUP BY m.thread_id ORDER BY MAX(m.created_at) DESC "
                "LIMIT %(limit)s OFFSET %(offset)s",
                params,
            )
            ids = [item[0] for item in cursor.fetchall()]
            if not ids:
                return [], {}, total
            params["threads"] = ids
            cursor.execute(
                "SELECT * FROM (" + _SELECT + f" WHERE {where} AND m.thread_id = ANY(%(threads)s) "
                ") latest",
                params,
            )
            rows = [_row(item) for item in cursor.fetchall()]
            newest: dict[UUID, MailRow] = {}
            for item in rows:
                current = newest.get(item.thread_id)
                if current is None or item.created_at > current.created_at:
                    newest[item.thread_id] = item
            shown = _SHOWN_IN_TRASH if folder == "TRASH" else _SHOWN
            cursor.execute(
                "SELECT m.thread_id, COUNT(*)::int, "
                f"BOOL_OR({_mine_as_recipient('AND r.read_at IS NULL AND r.deleted_at IS NULL')}), "
                f"BOOL_OR({_mine_as_recipient('AND r.starred_at IS NOT NULL')} "
                "OR (m.sender_id = %(me)s AND m.sender_starred_at IS NOT NULL)), "
                "BOOL_OR(EXISTS (SELECT 1 FROM mail_attachments a WHERE a.message_id = m.id)), "
                "ARRAY_AGG(COALESCE(su.name, 'Adverse') ORDER BY m.created_at) "
                "FROM mail_messages m LEFT JOIN users su ON su.id = m.sender_id "
                f"WHERE m.company_id = %(company)s AND m.thread_id = ANY(%(threads)s) "
                f"AND ({shown} OR {FOLDER_SQL[folder]}) GROUP BY m.thread_id",
                params,
            )
            stats = {
                item[0]: ThreadStats(
                    count=int(item[1]),
                    unread=bool(item[2]),
                    starred=bool(item[3]),
                    files=bool(item[4]),
                    participants=list(dict.fromkeys(item[5] or [])),
                )
                for item in cursor.fetchall()
            }
        return [newest[thread] for thread in ids if thread in newest], stats, total

    def thread(
        self, company_id: UUID, me: UUID, thread_id: UUID, trash: bool = False
    ) -> builtins.list[MailRow]:
        shown = _SHOWN_IN_TRASH if trash else _SHOWN
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                _SELECT + " WHERE m.company_id = %(company)s AND m.thread_id = %(thread)s "
                f"AND {shown} ORDER BY m.created_at",
                {"company": company_id, "me": me, "thread": thread_id},
            )
            return [_row(item) for item in cursor.fetchall()]

    def get(self, company_id: UUID, me: UUID, message_id: UUID) -> MailRow | None:
        """A message I can see in any folder (drafts included)."""
        visible = (
            f"({FOLDER_SQL['ALL']} OR {FOLDER_SQL['TRASH']} OR "
            f"({_MINE} AND m.status IN ('DRAFT', 'SCHEDULED')))"
        )
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                _SELECT + f" WHERE m.company_id = %(company)s AND m.id = %(id)s AND {visible}",
                {"company": company_id, "me": me, "id": message_id},
            )
            row = cursor.fetchone()
            return _row(row) if row else None

    def mark_thread_read(self, me: UUID, thread_id: UUID) -> int:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "UPDATE mail_recipients r SET read_at = NOW() AT TIME ZONE 'UTC' "
                "FROM mail_messages m WHERE m.id = r.message_id AND m.thread_id = %s "
                "AND m.status = 'SENT' AND r.user_id = %s AND r.read_at IS NULL",
                (thread_id, me),
            )
            return cursor.rowcount

    def act(self, company_id: UUID, me: UUID, thread_ids: builtins.list[UUID], action: str) -> int:
        """Apply a mailbox action to my copy of whole conversations."""
        now = "NOW() AT TIME ZONE 'UTC'"
        recipient = {
            "archive": f"archived_at = {now}",
            "inbox": "archived_at = NULL, deleted_at = NULL",
            "trash": f"deleted_at = {now}",
            "restore": "deleted_at = NULL",
            "purge": f"purged_at = {now}",
            "star": f"starred_at = {now}",
            "unstar": "starred_at = NULL",
            "read": f"read_at = COALESCE(read_at, {now})",
            "unread": "read_at = NULL",
        }[action]
        recipient_where = {
            "purge": " AND r.deleted_at IS NOT NULL",
            "star": " AND r.starred_at IS NULL",
        }.get(action, "")
        sender = {
            "trash": f"sender_deleted_at = {now}",
            "inbox": "sender_deleted_at = NULL",
            "restore": "sender_deleted_at = NULL",
            "purge": f"sender_purged_at = {now}",
            "star": f"sender_starred_at = {now}",
            "unstar": "sender_starred_at = NULL",
        }.get(action)
        sender_where = " AND sender_deleted_at IS NOT NULL" if action == "purge" else ""
        changed = 0
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                f"UPDATE mail_recipients r SET {recipient} FROM mail_messages m "
                "WHERE m.id = r.message_id AND m.company_id = %s AND m.thread_id = ANY(%s) "
                f"AND m.status = 'SENT' AND r.user_id = %s AND r.purged_at IS NULL{recipient_where}",
                (company_id, thread_ids, me),
            )
            changed += cursor.rowcount
            if sender:
                cursor.execute(
                    f"UPDATE mail_messages SET {sender} WHERE company_id = %s "
                    "AND thread_id = ANY(%s) AND sender_id = %s AND sender_purged_at IS NULL "
                    f"AND status = 'SENT'{sender_where}",
                    (company_id, thread_ids, me),
                )
                changed += cursor.rowcount
        return changed

    def hide(self, me: UUID, message_id: UUID) -> None:
        """Move one mail to my trash (others keep theirs)."""
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

    def counts(self, company_id: UUID, me: UUID) -> dict[str, int]:
        """Unread conversations in Inbox and Updates; drafts and scheduled mail."""
        params = {"company": company_id, "me": me}
        unread = _mine_as_recipient(
            "AND r.read_at IS NULL AND r.deleted_at IS NULL AND r.archived_at IS NULL"
        )
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT "
                f"COUNT(DISTINCT m.thread_id) FILTER (WHERE {FOLDER_SQL['INBOX']} AND {unread}), "
                f"COUNT(DISTINCT m.thread_id) FILTER (WHERE {FOLDER_SQL['UPDATES']} AND {unread}), "
                f"COUNT(*) FILTER (WHERE {FOLDER_SQL['DRAFTS']}), "
                f"COUNT(*) FILTER (WHERE {FOLDER_SQL['SCHEDULED']}) "
                "FROM mail_messages m WHERE m.company_id = %(company)s",
                params,
            )
            row = cursor.fetchone() or (0, 0, 0, 0)
        return {
            "INBOX": int(row[0]),
            "UPDATES": int(row[1]),
            "DRAFTS": int(row[2]),
            "SCHEDULED": int(row[3]),
        }

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

    # -- tickets ----------------------------------------------------------------------------

    def create_ticket(
        self, company_id: UUID, thread_id: UUID, subject: str, priority: str, raised_by: UUID
    ) -> UUID:
        ticket_id = uuid4()
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"ticket:{company_id}",))
            cursor.execute(
                "INSERT INTO mail_tickets (id, company_id, number, thread_id, subject, priority, "
                "raised_by_id, created_at, updated_at) VALUES (%s, %s, "
                "(SELECT COALESCE(MAX(number), 0) + 1 FROM mail_tickets WHERE company_id = %s), "
                "%s, %s, %s, %s, NOW() AT TIME ZONE 'UTC', NOW() AT TIME ZONE 'UTC')",
                (ticket_id, company_id, company_id, thread_id, subject, priority, raised_by),
            )
        return ticket_id

    def tickets(
        self, company_id: UUID, me: UUID | None, status: str | None
    ) -> builtins.list[TicketRow]:
        """me=None: every ticket (admin); otherwise the ones I raised or am assigned."""
        where = "t.company_id = %(company)s"
        if me is not None:
            where += " AND (t.raised_by_id = %(me)s OR t.assignee_id = %(me)s)"
        if status:
            where += " AND t.status = %(status)s"
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                _TICKET + f" WHERE {where} ORDER BY (t.status = 'CLOSED'), t.updated_at DESC "
                "LIMIT 300",
                {"company": company_id, "me": me, "status": status},
            )
            return [TicketRow(*row) for row in cursor.fetchall()]

    def ticket(self, company_id: UUID, ticket_id: UUID) -> TicketRow | None:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                _TICKET + " WHERE t.company_id = %s AND t.id = %s", (company_id, ticket_id)
            )
            row = cursor.fetchone()
            return TicketRow(*row) if row else None

    def ticket_for_threads(
        self, company_id: UUID, thread_ids: builtins.list[UUID]
    ) -> dict[UUID, TicketRow]:
        if not thread_ids:
            return {}
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                _TICKET + " WHERE t.company_id = %s AND t.thread_id = ANY(%s)",
                (company_id, thread_ids),
            )
            return {row[2]: TicketRow(*row) for row in cursor.fetchall()}

    def update_ticket(self, ticket_id: UUID, changes: dict[str, Any]) -> None:
        allowed = {"status", "priority", "assignee_id"}
        sets = [f"{key} = %({key})s" for key in changes if key in allowed]
        if not sets:
            return
        if "status" in changes:
            sets.append(
                "closed_at = CASE WHEN %(closing)s THEN NOW() AT TIME ZONE 'UTC' ELSE NULL END"
            )
        sets.append("updated_at = NOW() AT TIME ZONE 'UTC'")
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                f"UPDATE mail_tickets SET {', '.join(sets)} WHERE id = %(id)s",
                {**changes, "id": ticket_id, "closing": changes.get("status") == "CLOSED"},
            )

    def ticket_counts(self, company_id: UUID, me: UUID | None) -> dict[str, int]:
        where = "company_id = %(company)s"
        if me is not None:
            where += " AND (raised_by_id = %(me)s OR assignee_id = %(me)s)"
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                f"SELECT status, COUNT(*)::int FROM mail_tickets WHERE {where} GROUP BY status",
                {"company": company_id, "me": me},
            )
            return {row[0]: row[1] for row in cursor.fetchall()}

    def add_to_thread(self, thread_id: UUID, user_id: UUID) -> None:
        """Someone newly assigned to a ticket gets the conversation so far (already read)."""
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO mail_recipients (id, message_id, user_id, kind, read_at, created_at) "
                "SELECT gen_random_uuid(), m.id, %s, 'CC', NOW() AT TIME ZONE 'UTC', "
                "NOW() AT TIME ZONE 'UTC' FROM mail_messages m WHERE m.thread_id = %s "
                "AND m.status = 'SENT' AND (m.sender_id IS NULL OR m.sender_id <> %s) "
                "ON CONFLICT (message_id, user_id) DO NOTHING",
                (user_id, thread_id, user_id),
            )
