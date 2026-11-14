"""Storage for chat (Phase 14)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from app.database.connectivity import database_pool


@dataclass(frozen=True)
class PersonRef:
    id: UUID
    name: str
    role: str  # role code, e.g. COMPANY_ADMIN
    image: str | None


@dataclass(frozen=True)
class ConversationRow:
    id: UUID
    type: str
    title: str
    client_id: UUID | None
    client_name: str | None
    created_by_id: UUID
    last_message_at: datetime | None
    created_at: datetime
    last_id: UUID | None
    last_body: str | None
    last_sender_id: UUID | None
    last_sender_name: str | None
    last_created_at: datetime | None
    last_deleted: bool
    last_files: int
    my_last_read_at: datetime | None
    unread: int


@dataclass(frozen=True)
class MemberRow:
    conversation_id: UUID
    user_id: UUID
    name: str
    role: str
    image: str | None
    last_read_at: datetime | None


@dataclass(frozen=True)
class AttachmentRow:
    id: UUID
    message_id: UUID
    file_name: str
    storage_path: str
    mime_type: str
    size_bytes: int


@dataclass(frozen=True)
class MessageRow:
    id: UUID
    conversation_id: UUID
    sender_id: UUID
    sender_name: str
    sender_role: str
    sender_image: str | None
    body: str
    reply_to_id: UUID | None
    reply_sender_name: str | None
    reply_body: str | None
    reply_deleted: bool
    edited_at: datetime | None
    deleted_at: datetime | None
    created_at: datetime


_USER_ROLE = "JOIN roles r ON r.id = u.role_id"
_ACTIVE = "u.status IN ('ACTIVE', 'PENDING_VERIFICATION')"

_CONVERSATION_SELECT = """
SELECT c.id, c.type::text, c.title, c.client_id, cl.name, c.created_by_id, c.last_message_at,
  c.created_at, lm.id, lm.body, lm.sender_id, su.name, lm.created_at, lm.deleted_at IS NOT NULL,
  COALESCE((SELECT COUNT(*) FROM chat_attachments a WHERE a.message_id = lm.id), 0),
  me.last_read_at,
  (SELECT COUNT(*) FROM chat_messages m
    WHERE m.conversation_id = c.id AND m.sender_id <> %(user)s AND m.deleted_at IS NULL
      AND (me.last_read_at IS NULL OR m.created_at > me.last_read_at))
FROM chat_conversations c
LEFT JOIN clients cl ON cl.id = c.client_id
LEFT JOIN chat_members me ON me.conversation_id = c.id AND me.user_id = %(user)s
LEFT JOIN LATERAL (
  SELECT m.* FROM chat_messages m WHERE m.conversation_id = c.id
  ORDER BY m.created_at DESC LIMIT 1
) lm ON TRUE
LEFT JOIN users su ON su.id = lm.sender_id
"""

_MESSAGE_SELECT = """
SELECT m.id, m.conversation_id, m.sender_id, su.name, sr.code, su.profile_image_url, m.body,
  m.reply_to_id, ru.name, rm.body, rm.deleted_at IS NOT NULL, m.edited_at, m.deleted_at,
  m.created_at
FROM chat_messages m
JOIN users su ON su.id = m.sender_id
JOIN roles sr ON sr.id = su.role_id
LEFT JOIN chat_messages rm ON rm.id = m.reply_to_id
LEFT JOIN users ru ON ru.id = rm.sender_id
"""


def _conversation(row: tuple[Any, ...]) -> ConversationRow:
    values = list(row)
    values[14] = int(values[14])
    values[16] = int(values[16])
    return ConversationRow(*values)


class ChatRepository:
    # -- people and access -----------------------------------------------------------------

    def person(self, company_id: UUID, user_id: UUID) -> PersonRef | None:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                f"SELECT u.id, u.name, r.code, u.profile_image_url FROM users u {_USER_ROLE} "
                "WHERE u.company_id = %s AND u.id = %s",
                (company_id, user_id),
            )
            row = cursor.fetchone()
            return PersonRef(*row) if row else None

    def people(self, company_id: UUID, roles: tuple[str, ...]) -> list[PersonRef]:
        """Active people of the company with one of these role codes."""
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                f"SELECT u.id, u.name, r.code, u.profile_image_url FROM users u {_USER_ROLE} "
                f"WHERE u.company_id = %s AND {_ACTIVE} AND r.code = ANY(%s) ORDER BY u.name",
                (company_id, list(roles)),
            )
            return [PersonRef(*row) for row in cursor.fetchall()]

    def client_for_user(self, company_id: UUID, user_id: UUID) -> UUID | None:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM clients WHERE company_id = %s AND user_id = %s",
                (company_id, user_id),
            )
            row = cursor.fetchone()
            return row[0] if row else None

    def client_exists(self, company_id: UUID, client_id: UUID) -> bool:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM clients WHERE company_id = %s AND id = %s", (company_id, client_id)
            )
            return cursor.fetchone() is not None

    def client_user(self, company_id: UUID, client_id: UUID) -> tuple[str, UUID | None] | None:
        """A client's name and login (None when the client has no portal login yet)."""
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT name, user_id FROM clients WHERE company_id = %s AND id = %s",
                (company_id, client_id),
            )
            row = cursor.fetchone()
            return (row[0], row[1]) if row else None

    def admin_ids(self, company_id: UUID) -> list[UUID]:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                f"SELECT u.id FROM users u {_USER_ROLE} WHERE u.company_id = %s "
                f"AND {_ACTIVE} AND r.code = 'COMPANY_ADMIN'",
                (company_id,),
            )
            return [row[0] for row in cursor.fetchall()]

    def statuses(self, user_ids: list[UUID]) -> dict[UUID, str]:
        if not user_ids:
            return {}
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT user_id, status::text FROM chat_statuses WHERE user_id = ANY(%s)",
                (user_ids,),
            )
            return {row[0]: row[1] for row in cursor.fetchall()}

    def set_status(self, user_id: UUID, status: str) -> None:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO chat_statuses (user_id, status, updated_at) "
                'VALUES (%s, %s::"ChatStatusValue", NOW()) '
                "ON CONFLICT (user_id) DO UPDATE SET status = EXCLUDED.status, updated_at = NOW()",
                (user_id, status),
            )
            connection.commit()

    # -- conversations ---------------------------------------------------------------------

    def list_conversations(
        self, company_id: UUID, user_id: UUID, admin: bool
    ) -> list[ConversationRow]:
        """Chats the person is in; an admin also sees every client room."""
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                _CONVERSATION_SELECT
                + """
                WHERE c.company_id = %(company)s
                  AND (me.is_member OR (c.type = 'CLIENT' AND %(admin)s))
                ORDER BY COALESCE(c.last_message_at, c.created_at) DESC
                """,
                {"company": company_id, "user": user_id, "admin": admin},
            )
            return [_conversation(row) for row in cursor.fetchall()]

    def get_conversation(
        self, company_id: UUID, conversation_id: UUID, user_id: UUID
    ) -> ConversationRow | None:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                _CONVERSATION_SELECT + " WHERE c.company_id = %(company)s AND c.id = %(id)s",
                {"company": company_id, "user": user_id, "id": conversation_id},
            )
            row = cursor.fetchone()
            return _conversation(row) if row else None

    def is_member(self, conversation_id: UUID, user_id: UUID) -> bool:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT is_member FROM chat_members WHERE conversation_id = %s AND user_id = %s",
                (conversation_id, user_id),
            )
            row = cursor.fetchone()
            return bool(row and row[0])

    def members(self, conversation_ids: list[UUID]) -> list[MemberRow]:
        """Members of chats, with read state."""
        if not conversation_ids:
            return []
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT cm.conversation_id, u.id, u.name, r.code, u.profile_image_url, cm.last_read_at
                FROM chat_members cm JOIN users u ON u.id = cm.user_id {_USER_ROLE}
                WHERE cm.conversation_id = ANY(%s) AND cm.is_member
                ORDER BY u.name
                """,
                (conversation_ids,),
            )
            return [MemberRow(*row) for row in cursor.fetchall()]

    def read_marks(self, conversation_id: UUID) -> dict[UUID, datetime | None]:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT user_id, last_read_at FROM chat_members WHERE conversation_id = %s",
                (conversation_id,),
            )
            return {row[0]: row[1] for row in cursor.fetchall()}

    def direct(self, company_id: UUID, key: str, user_ids: list[UUID], actor_id: UUID) -> UUID:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO chat_conversations (id, company_id, type, direct_key, created_by_id, "
                "updated_at) VALUES (%s, %s, 'DIRECT', %s, %s, NOW()) "
                "ON CONFLICT (company_id, direct_key) DO NOTHING",
                (uuid4(), company_id, key, actor_id),
            )
            cursor.execute(
                "SELECT id FROM chat_conversations WHERE company_id = %s AND direct_key = %s",
                (company_id, key),
            )
            row = cursor.fetchone()
            assert row is not None
            conversation_id: UUID = row[0]
            self._join(cursor, conversation_id, user_ids)
            connection.commit()
        return conversation_id

    def create_group(
        self,
        company_id: UUID,
        title: str,
        user_ids: list[UUID],
        actor_id: UUID,
        client_id: UUID | None = None,
    ) -> UUID:
        """A staff group, or (with a client) a client room."""
        conversation_id = uuid4()
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO chat_conversations (id, company_id, type, title, client_id, "
                "created_by_id, updated_at) VALUES (%s, %s, %s, %s, %s, %s, NOW())",
                (
                    conversation_id,
                    company_id,
                    "CLIENT" if client_id else "GROUP",
                    title,
                    client_id,
                    actor_id,
                ),
            )
            self._join(cursor, conversation_id, user_ids)
            connection.commit()
        return conversation_id

    def update_group(
        self, conversation_id: UUID, title: str | None, user_ids: list[UUID] | None
    ) -> None:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            if title is not None:
                cursor.execute(
                    "UPDATE chat_conversations SET title = %s, updated_at = NOW() WHERE id = %s",
                    (title, conversation_id),
                )
            if user_ids is not None:
                cursor.execute(
                    "UPDATE chat_members SET is_member = (user_id = ANY(%s)) "
                    "WHERE conversation_id = %s",
                    (user_ids, conversation_id),
                )
                self._join(cursor, conversation_id, user_ids)
            connection.commit()

    @staticmethod
    def _join(cursor: Any, conversation_id: UUID, user_ids: list[UUID]) -> None:
        for user_id in user_ids:
            cursor.execute(
                "INSERT INTO chat_members (id, conversation_id, user_id, is_member) "
                "VALUES (%s, %s, %s, TRUE) ON CONFLICT (conversation_id, user_id) "
                "DO UPDATE SET is_member = TRUE",
                (uuid4(), conversation_id, user_id),
            )

    def mark_read(self, conversation_id: UUID, user_id: UUID, member: bool) -> datetime:
        """Store that the user has read everything so far. An admin reading a client room they
        were not added to gets a row with is_member = false (read state only)."""
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO chat_members (id, conversation_id, user_id, is_member, last_read_at) "
                "VALUES (%s, %s, %s, %s, NOW()) ON CONFLICT (conversation_id, user_id) "
                "DO UPDATE SET last_read_at = NOW() RETURNING last_read_at",
                (uuid4(), conversation_id, user_id, member),
            )
            row = cursor.fetchone()
            connection.commit()
            assert row is not None
            stamp: datetime = row[0]
            return stamp

    # -- messages --------------------------------------------------------------------------

    def messages(
        self, conversation_id: UUID, before: datetime | None, limit: int
    ) -> list[MessageRow]:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                _MESSAGE_SELECT
                + " WHERE m.conversation_id = %s AND (%s::timestamp IS NULL OR m.created_at < %s)"
                " ORDER BY m.created_at DESC LIMIT %s",
                (conversation_id, before, before, limit),
            )
            return [MessageRow(*row) for row in reversed(cursor.fetchall())]

    def message(self, company_id: UUID, message_id: UUID) -> MessageRow | None:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                _MESSAGE_SELECT + " WHERE m.company_id = %s AND m.id = %s", (company_id, message_id)
            )
            row = cursor.fetchone()
            return MessageRow(*row) if row else None

    def attachments(self, message_ids: list[UUID]) -> list[AttachmentRow]:
        if not message_ids:
            return []
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, message_id, file_name, storage_path, mime_type, size_bytes "
                "FROM chat_attachments WHERE message_id = ANY(%s) ORDER BY created_at",
                (message_ids,),
            )
            return [
                AttachmentRow(row[0], row[1], row[2], row[3], row[4], int(row[5]))
                for row in cursor.fetchall()
            ]

    def attachment(self, attachment_id: UUID) -> tuple[AttachmentRow, UUID] | None:
        """An attachment and its conversation."""
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT a.id, a.message_id, a.file_name, a.storage_path, a.mime_type, a.size_bytes, "
                "m.conversation_id FROM chat_attachments a JOIN chat_messages m ON m.id = a.message_id "
                "WHERE a.id = %s AND m.deleted_at IS NULL",
                (attachment_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return AttachmentRow(row[0], row[1], row[2], row[3], row[4], int(row[5])), row[6]

    def add_message(
        self,
        company_id: UUID,
        conversation_id: UUID,
        sender_id: UUID,
        body: str,
        reply_to_id: UUID | None,
        files: list[tuple[str, str, str, int]],
    ) -> UUID:
        message_id = uuid4()
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO chat_messages (id, company_id, conversation_id, sender_id, body, "
                "reply_to_id) VALUES (%s, %s, %s, %s, %s, %s) RETURNING created_at",
                (message_id, company_id, conversation_id, sender_id, body, reply_to_id),
            )
            for name, path, mime, size in files:
                cursor.execute(
                    "INSERT INTO chat_attachments (id, message_id, file_name, storage_path, "
                    "mime_type, size_bytes) VALUES (%s, %s, %s, %s, %s, %s)",
                    (uuid4(), message_id, name, path, mime, size),
                )
            cursor.execute(
                "UPDATE chat_conversations SET last_message_at = NOW(), updated_at = NOW() "
                "WHERE id = %s",
                (conversation_id,),
            )
            connection.commit()
        return message_id

    def edit_message(self, message_id: UUID, body: str) -> None:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "UPDATE chat_messages SET body = %s, edited_at = NOW() WHERE id = %s",
                (body, message_id),
            )
            connection.commit()

    def delete_message(self, message_id: UUID) -> list[str]:
        """Soft-delete the message; its attachments are removed. Returns their storage paths."""
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM chat_attachments WHERE message_id = %s RETURNING storage_path",
                (message_id,),
            )
            paths = [row[0] for row in cursor.fetchall()]
            cursor.execute(
                "UPDATE chat_messages SET body = '', deleted_at = NOW() WHERE id = %s",
                (message_id,),
            )
            connection.commit()
        return paths

    def reactions(self, message_ids: list[UUID]) -> list[tuple[UUID, UUID, str]]:
        """(message, user, emoji) for these messages, oldest first."""
        if not message_ids:
            return []
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT message_id, user_id, emoji FROM chat_reactions "
                "WHERE message_id = ANY(%s) ORDER BY created_at",
                (message_ids,),
            )
            return [(row[0], row[1], row[2]) for row in cursor.fetchall()]

    def toggle_reaction(self, message_id: UUID, user_id: UUID, emoji: str) -> None:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM chat_reactions WHERE message_id = %s AND user_id = %s AND emoji = %s",
                (message_id, user_id, emoji),
            )
            if not cursor.rowcount:
                cursor.execute(
                    "INSERT INTO chat_reactions (id, message_id, user_id, emoji) "
                    "VALUES (%s, %s, %s, %s)",
                    (uuid4(), message_id, user_id, emoji),
                )
            connection.commit()

    def search(
        self, company_id: UUID, user_id: UUID, admin: bool, text: str, limit: int
    ) -> list[MessageRow]:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                _MESSAGE_SELECT
                + """
                JOIN chat_conversations c ON c.id = m.conversation_id
                LEFT JOIN chat_members me ON me.conversation_id = c.id AND me.user_id = %(user)s
                WHERE m.company_id = %(company)s AND m.deleted_at IS NULL
                  AND m.body ILIKE %(text)s
                  AND (me.is_member OR (c.type = 'CLIENT' AND %(admin)s))
                ORDER BY m.created_at DESC LIMIT %(limit)s
                """,
                {
                    "company": company_id,
                    "user": user_id,
                    "admin": admin,
                    "text": "%"
                    + text.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")
                    + "%",
                    "limit": limit,
                },
            )
            return [MessageRow(*row) for row in cursor.fetchall()]
