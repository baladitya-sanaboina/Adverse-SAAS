"""Storage for chat calls and scheduled meetings (Phase 14, owner request 2026-11-14)."""

from __future__ import annotations

import secrets
import string
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from app.database.connectivity import database_pool

# A participant whose browser has not checked in for this long has left (closed tab, lost network).
STALE_SECONDS = 45
# Someone waiting in the lobby whose page has not checked in for this long has gone away.
LOBBY_STALE_SECONDS = 30


def new_meet_code() -> str:
    """A Meet-style code such as "kfr-wqzt-bmd" (26^10 values, so not guessable by listing)."""
    letters = [secrets.choice(string.ascii_lowercase) for _ in range(10)]
    return f"{''.join(letters[:3])}-{''.join(letters[3:7])}-{''.join(letters[7:])}"


@dataclass(frozen=True)
class CallRow:
    id: UUID
    conversation_id: UUID
    kind: str
    started_by_id: UUID
    started_at: datetime
    ended_at: datetime | None
    meet_code: str | None


@dataclass(frozen=True)
class SeatRow:
    user_id: UUID
    name: str
    role: str
    image: str | None
    joined_at: datetime


@dataclass(frozen=True)
class WaitingRow:
    user_id: UUID
    name: str
    role: str
    image: str | None
    requested_at: datetime


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
    meet_code: str | None


_CALL = (
    "SELECT id, conversation_id, kind::text, started_by_id, started_at, ended_at, "
    "(SELECT meet_code FROM chat_conversations c WHERE c.id = chat_calls.conversation_id) "
    "FROM chat_calls"
)

_MEETING = """
SELECT mt.id, mt.conversation_id, c.type::text, c.title, cl.name, mt.title, mt.notes, mt.starts_at,
  mt.duration_minutes, mt.kind::text, mt.created_by_id, u.name, mt.cancelled_at, c.meet_code
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

    # -- meet links and the lobby -------------------------------------------------------------

    def meet_code(self, conversation_id: UUID) -> str:
        """The chat's meet link code, made on first use."""
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT meet_code FROM chat_conversations WHERE id = %s FOR UPDATE",
                (conversation_id,),
            )
            row = cursor.fetchone()
            if row and row[0]:
                connection.commit()
                return str(row[0])
            while True:
                code = new_meet_code()
                cursor.execute("SELECT 1 FROM chat_conversations WHERE meet_code = %s", (code,))
                if cursor.fetchone() is None:
                    break
            cursor.execute(
                "UPDATE chat_conversations SET meet_code = %s WHERE id = %s",
                (code, conversation_id),
            )
            connection.commit()
        return code

    def by_code(self, company_id: UUID, code: str) -> UUID | None:
        """The chat a meet code belongs to, only inside the person's own company."""
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM chat_conversations WHERE company_id = %s AND meet_code = %s",
                (company_id, code),
            )
            row = cursor.fetchone()
            return row[0] if row else None

    def admission(self, call_id: UUID, user_id: UUID) -> str | None:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT status::text FROM chat_call_admissions WHERE call_id = %s AND user_id = %s",
                (call_id, user_id),
            )
            row = cursor.fetchone()
            return str(row[0]) if row else None

    def knock(self, call_id: UUID, user_id: UUID) -> tuple[str, bool]:
        """Ask to join, or say "still waiting". Returns (status, new) where new means the hosts
        have not been told yet. A decision already made is kept."""
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT status::text, last_seen_at < NOW() - make_interval(secs => %s) "
                "FROM chat_call_admissions WHERE call_id = %s AND user_id = %s FOR UPDATE",
                (LOBBY_STALE_SECONDS, call_id, user_id),
            )
            row = cursor.fetchone()
            if row is None:
                cursor.execute(
                    "INSERT INTO chat_call_admissions (id, call_id, user_id) VALUES (%s, %s, %s)",
                    (uuid4(), call_id, user_id),
                )
                connection.commit()
                return "WAITING", True
            status, stale = str(row[0]), bool(row[1])
            if status == "WAITING":
                cursor.execute(
                    "UPDATE chat_call_admissions SET last_seen_at = NOW()"
                    + (", requested_at = NOW()" if stale else "")
                    + " WHERE call_id = %s AND user_id = %s",
                    (call_id, user_id),
                )
            connection.commit()
        return status, status == "WAITING" and stale

    def withdraw(self, call_id: UUID, user_id: UUID) -> None:
        """Stop waiting (closed the lobby page)."""
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM chat_call_admissions "
                "WHERE call_id = %s AND user_id = %s AND status = 'WAITING'",
                (call_id, user_id),
            )
            connection.commit()

    def waiting(self, call_id: UUID) -> list[WaitingRow]:
        """People waiting in the lobby right now."""
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT u.id, u.name, r.code, u.profile_image_url, a.requested_at
                FROM chat_call_admissions a
                JOIN users u ON u.id = a.user_id JOIN roles r ON r.id = u.role_id
                WHERE a.call_id = %s AND a.status = 'WAITING'
                  AND a.last_seen_at >= NOW() - make_interval(secs => %s)
                ORDER BY a.requested_at
                """,
                (call_id, LOBBY_STALE_SECONDS),
            )
            return [WaitingRow(*row) for row in cursor.fetchall()]

    def decide(self, call_id: UUID, user_id: UUID, status: str, decided_by: UUID) -> bool:
        """Admit or deny someone who is waiting. False when they were not waiting."""
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                'UPDATE chat_call_admissions SET status = %s::"ChatCallAdmissionStatus", '
                "decided_at = NOW(), decided_by_id = %s "
                "WHERE call_id = %s AND user_id = %s AND status = 'WAITING'",
                (status, decided_by, call_id, user_id),
            )
            changed = cursor.rowcount > 0
            connection.commit()
        return changed

    def admitted(self, call_id: UUID) -> list[UUID]:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT user_id FROM chat_call_admissions "
                "WHERE call_id = %s AND status = 'ADMITTED'",
                (call_id,),
            )
            return [row[0] for row in cursor.fetchall()]

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
