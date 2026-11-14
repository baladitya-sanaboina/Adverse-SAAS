"""Storage for chat calls and scheduled meetings (Phase 14, owner request 2026-11-14)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from app.database.connectivity import database_pool

# A participant whose browser has not checked in for this long has left (closed tab, lost network).
STALE_SECONDS = 45


@dataclass(frozen=True)
class CallRow:
    id: UUID
    conversation_id: UUID
    kind: str
    started_by_id: UUID
    started_at: datetime
    ended_at: datetime | None


@dataclass(frozen=True)
class SeatRow:
    user_id: UUID
    name: str
    role: str
    image: str | None
    joined_at: datetime


@dataclass(frozen=True)
class MeetingRow:
    id: UUID
    conversation_id: UUID
    conversation_type: str
    conversation_title: str
    client_name: str | None
    title: str
    notes: str
    starts_at: datetime
    duration_minutes: int
    kind: str
    created_by_id: UUID
    created_by_name: str
    cancelled_at: datetime | None


_CALL = (
    "SELECT id, conversation_id, kind::text, started_by_id, started_at, ended_at FROM chat_calls"
)

_MEETING = """
SELECT mt.id, mt.conversation_id, c.type::text, c.title, cl.name, mt.title, mt.notes, mt.starts_at,
  mt.duration_minutes, mt.kind::text, mt.created_by_id, u.name, mt.cancelled_at
FROM chat_meetings mt
JOIN chat_conversations c ON c.id = mt.conversation_id
LEFT JOIN clients cl ON cl.id = c.client_id
JOIN users u ON u.id = mt.created_by_id
"""


class CallRepository:
    # -- calls -----------------------------------------------------------------------------

    def get(self, call_id: UUID) -> CallRow | None:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(_CALL + " WHERE id = %s", (call_id,))
            row = cursor.fetchone()
            return CallRow(*row) if row else None

    def active(self, conversation_id: UUID) -> CallRow | None:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                _CALL + " WHERE conversation_id = %s AND ended_at IS NULL "
                "ORDER BY started_at DESC LIMIT 1",
                (conversation_id,),
            )
            row = cursor.fetchone()
            return CallRow(*row) if row else None

    def start(
        self, company_id: UUID, conversation_id: UUID, user_id: UUID, kind: str
    ) -> tuple[UUID, bool]:
        """The chat's running call, or a new one. Returns (call id, created). The chat row is
        locked so two people pressing Call at once end up in the same call."""
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM chat_conversations WHERE id = %s FOR UPDATE", (conversation_id,)
            )
            cursor.execute(
                "SELECT id FROM chat_calls WHERE conversation_id = %s AND ended_at IS NULL "
                "ORDER BY started_at DESC LIMIT 1",
                (conversation_id,),
            )
            row = cursor.fetchone()
            if row:
                connection.commit()
                return row[0], False
            call_id = uuid4()
            cursor.execute(
                "INSERT INTO chat_calls (id, company_id, conversation_id, kind, started_by_id) "
                'VALUES (%s, %s, %s, %s::"ChatCallKind", %s)',
                (call_id, company_id, conversation_id, kind, user_id),
            )
            connection.commit()
        return call_id, True

    def join(self, call_id: UUID, user_id: UUID) -> None:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO chat_call_participants (id, call_id, user_id) VALUES (%s, %s, %s) "
                "ON CONFLICT (call_id, user_id) DO UPDATE SET left_at = NULL, "
                "last_seen_at = NOW(), joined_at = CASE WHEN chat_call_participants.left_at IS NULL "
                "THEN chat_call_participants.joined_at ELSE NOW() END",
                (uuid4(), call_id, user_id),
            )
            connection.commit()

    def leave(self, call_id: UUID, user_id: UUID) -> None:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "UPDATE chat_call_participants SET left_at = NOW() "
                "WHERE call_id = %s AND user_id = %s AND left_at IS NULL",
                (call_id, user_id),
            )
            connection.commit()

    def ping(self, call_id: UUID, user_id: UUID) -> bool:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "UPDATE chat_call_participants SET last_seen_at = NOW() "
                "WHERE call_id = %s AND user_id = %s AND left_at IS NULL",
                (call_id, user_id),
            )
            touched = cursor.rowcount > 0
            connection.commit()
        return touched

    def prune(self, call_id: UUID) -> None:
        """Mark people who stopped checking in as gone."""
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "UPDATE chat_call_participants SET left_at = last_seen_at "
                "WHERE call_id = %s AND left_at IS NULL "
                f"AND last_seen_at < NOW() - INTERVAL '{STALE_SECONDS} seconds'",
                (call_id,),
            )
            connection.commit()

    def seats(self, call_id: UUID) -> list[SeatRow]:
        """People in the call right now."""
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT u.id, u.name, r.code, u.profile_image_url, p.joined_at
                FROM chat_call_participants p
                JOIN users u ON u.id = p.user_id JOIN roles r ON r.id = u.role_id
                WHERE p.call_id = %s AND p.left_at IS NULL ORDER BY p.joined_at
                """,
                (call_id,),
            )
            return [SeatRow(*row) for row in cursor.fetchall()]

    def ever_joined(self, call_id: UUID) -> set[UUID]:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT user_id FROM chat_call_participants WHERE call_id = %s", (call_id,)
            )
            return {row[0] for row in cursor.fetchall()}

    def end(self, call_id: UUID) -> bool:
        """End the call once; returns False when it had already ended."""
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "UPDATE chat_calls SET ended_at = NOW() WHERE id = %s AND ended_at IS NULL",
                (call_id,),
            )
            ended = cursor.rowcount > 0
            cursor.execute(
                "UPDATE chat_call_participants SET left_at = NOW() "
                "WHERE call_id = %s AND left_at IS NULL",
                (call_id,),
            )
            connection.commit()
        return ended

    # -- meetings --------------------------------------------------------------------------

    def create_meeting(
        self,
        company_id: UUID,
        conversation_id: UUID,
        user_id: UUID,
        title: str,
        notes: str,
        starts_at: datetime,
        duration_minutes: int,
        kind: str,
    ) -> UUID:
        meeting_id = uuid4()
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO chat_meetings (id, company_id, conversation_id, title, notes, "
                "starts_at, duration_minutes, kind, created_by_id) "
                'VALUES (%s, %s, %s, %s, %s, %s, %s, %s::"ChatCallKind", %s)',
                (
                    meeting_id,
                    company_id,
                    conversation_id,
                    title,
                    notes,
                    starts_at,
                    duration_minutes,
                    kind,
                    user_id,
                ),
            )
            connection.commit()
        return meeting_id

    def meeting(self, company_id: UUID, meeting_id: UUID) -> MeetingRow | None:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                _MEETING + " WHERE mt.company_id = %s AND mt.id = %s", (company_id, meeting_id)
            )
            row = cursor.fetchone()
            return MeetingRow(*row) if row else None

    def meetings(
        self,
        company_id: UUID,
        user_id: UUID,
        admin: bool,
        start: datetime | None,
        end: datetime | None,
        conversation_id: UUID | None,
    ) -> list[MeetingRow]:
        """Meetings in chats this person can see (the same rule as the chat list)."""
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                _MEETING
                + """
                LEFT JOIN chat_members me ON me.conversation_id = c.id AND me.user_id = %(user)s
                WHERE mt.company_id = %(company)s AND mt.cancelled_at IS NULL
                  AND (me.is_member OR (c.type = 'CLIENT' AND %(admin)s))
                  AND (%(start)s::timestamp IS NULL
                       OR mt.starts_at + make_interval(mins => mt.duration_minutes) >= %(start)s)
                  AND (%(end)s::timestamp IS NULL OR mt.starts_at <= %(end)s)
                  AND (%(conversation)s::uuid IS NULL OR mt.conversation_id = %(conversation)s)
                ORDER BY mt.starts_at
                """,
                {
                    "company": company_id,
                    "user": user_id,
                    "admin": admin,
                    "start": start,
                    "end": end,
                    "conversation": conversation_id,
                },
            )
            return [MeetingRow(*row) for row in cursor.fetchall()]

    def cancel_meeting(self, meeting_id: UUID) -> None:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "UPDATE chat_meetings SET cancelled_at = NOW() WHERE id = %s AND cancelled_at IS NULL",
                (meeting_id,),
            )
            connection.commit()
