"""Calendar storage (owner request 2026-11-15): agenda_events, agenda_attendees, agenda_todos,
plus read-only views of task deadlines and chat meetings for the same calendar."""

from __future__ import annotations

import builtins
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

from app.database.connectivity import database_pool

NOW = "NOW() AT TIME ZONE 'UTC'"


@dataclass(frozen=True)
class EventRow:
    id: UUID
    company_id: UUID
    owner_id: UUID
    owner_name: str
    owner_role: str
    title: str
    notes: str
    location: str
    starts_at: datetime
    ends_at: datetime
    all_day: bool
    colour: str
    video: bool
    conversation_id: UUID | None
    meeting_id: UUID | None
    mail_thread_id: UUID | None
    attendees: list[tuple[UUID, str, str, str]]  # (id, name, role code, response)


@dataclass(frozen=True)
class TodoRow:
    id: UUID
    owner_id: UUID
    owner_name: str
    title: str
    notes: str
    due_date: date | None
    due_at: datetime | None
    priority: str
    done_at: datetime | None
    created_at: datetime


@dataclass(frozen=True)
class TaskDueRow:
    id: UUID
    number: int
    title: str
    due_date: date
    status: str
    assignee_id: UUID | None
    assignee_name: str | None
    client_name: str | None


@dataclass(frozen=True)
class MeetingDueRow:
    id: UUID
    conversation_id: UUID
    title: str
    starts_at: datetime
    duration_minutes: int
    kind: str
    room: str


@dataclass(frozen=True)
class AlertRow:
    kind: str  # EVENT or TODO
    moment: str  # BEFORE or START
    id: UUID
    company_id: UUID
    title: str
    starts_at: datetime
    people: list[UUID]
    video: bool
    conversation_id: UUID | None


_EVENT = """
    SELECT e.id, e.company_id, e.owner_id, ou.name, orl.code, e.title, e.notes, e.location,
      e.starts_at, e.ends_at, e.all_day, e.colour, e.video, e.conversation_id, e.meeting_id,
      e.mail_thread_id,
      COALESCE((
        SELECT json_agg(json_build_array(u.id, u.name, r.code, a.response) ORDER BY u.name)
        FROM agenda_attendees a JOIN users u ON u.id = a.user_id JOIN roles r ON r.id = u.role_id
        WHERE a.event_id = e.id
      ), '[]'::json)
    FROM agenda_events e
    JOIN users ou ON ou.id = e.owner_id
    JOIN roles orl ON orl.id = ou.role_id
"""

_TODO = """
    SELECT t.id, t.owner_id, u.name, t.title, t.notes, t.due_date, t.due_at, t.priority,
      t.done_at, t.created_at
    FROM agenda_todos t JOIN users u ON u.id = t.owner_id
"""


def _event(row: tuple[Any, ...]) -> EventRow:
    data = list(row)
    data[16] = [(UUID(str(a[0])), str(a[1]), str(a[2]), str(a[3])) for a in (data[16] or [])]
    return EventRow(*data)


class AgendaRepository:
    # -- people -----------------------------------------------------------------------------

    def team(self, company_id: UUID, manager_id: UUID) -> builtins.list[UUID]:
        """A manager's team: the people on the tasks they monitor."""
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT DISTINCT assignee_user_id FROM tasks WHERE company_id = %s "
                "AND monitor_user_id = %s AND assignee_user_id IS NOT NULL",
                (company_id, manager_id),
            )
            return [row[0] for row in cursor.fetchall()]

    # -- events -----------------------------------------------------------------------------

    def events(
        self, company_id: UUID, start: datetime, end: datetime, people: builtins.list[UUID] | None
    ) -> builtins.list[EventRow]:
        where = (
            "e.company_id = %(company)s AND e.cancelled_at IS NULL "
            "AND e.starts_at < %(end)s AND e.ends_at > %(start)s"
        )
        if people is not None:
            where += (
                " AND (e.owner_id = ANY(%(people)s) OR EXISTS (SELECT 1 FROM agenda_attendees a "
                "WHERE a.event_id = e.id AND a.user_id = ANY(%(people)s)))"
            )
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                _EVENT + f" WHERE {where} ORDER BY e.starts_at LIMIT 2000",
                {"company": company_id, "start": start, "end": end, "people": people},
            )
            return [_event(row) for row in cursor.fetchall()]

    def event(self, company_id: UUID, event_id: UUID) -> EventRow | None:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                _EVENT + " WHERE e.company_id = %s AND e.id = %s AND e.cancelled_at IS NULL",
                (company_id, event_id),
            )
            row = cursor.fetchone()
            return _event(row) if row else None

    def event_for_thread(self, company_id: UUID, thread_id: UUID) -> EventRow | None:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                _EVENT + " WHERE e.company_id = %s AND e.mail_thread_id = %s "
                "AND e.cancelled_at IS NULL ORDER BY e.created_at DESC LIMIT 1",
                (company_id, thread_id),
            )
            row = cursor.fetchone()
            return _event(row) if row else None

    def create_event(self, company_id: UUID, owner_id: UUID, fields: dict[str, Any]) -> UUID:
        event_id = uuid4()
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO agenda_events (id, company_id, owner_id, title, notes, location, "
                "starts_at, ends_at, all_day, colour, video, conversation_id, meeting_id, "
                f"mail_thread_id, created_at, updated_at) VALUES (%(id)s, %(company)s, %(owner)s, "
                "%(title)s, %(notes)s, %(location)s, %(starts_at)s, %(ends_at)s, %(all_day)s, "
                "%(colour)s, %(video)s, %(conversation_id)s, %(meeting_id)s, %(mail_thread_id)s, "
                f"{NOW}, {NOW})",
                {
                    "id": event_id,
                    "company": company_id,
                    "owner": owner_id,
                    "conversation_id": None,
                    "meeting_id": None,
                    "mail_thread_id": None,
                    **fields,
                },
            )
        return event_id

    def update_event(self, event_id: UUID, fields: dict[str, Any]) -> None:
        allowed = {
            "title",
            "notes",
            "location",
            "starts_at",
            "ends_at",
            "all_day",
            "colour",
            "video",
            "conversation_id",
            "meeting_id",
        }
        sets = [f"{key} = %({key})s" for key in fields if key in allowed]
        if not sets:
            return
        if "starts_at" in fields:
            # A new time means new alerts.
            sets += ["alerted_before_at = NULL", "alerted_start_at = NULL"]
        sets.append(f"updated_at = {NOW}")
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                f"UPDATE agenda_events SET {', '.join(sets)} WHERE id = %(event)s",
                {**fields, "event": event_id},
            )

    def set_attendees(self, event_id: UUID, people: builtins.list[UUID]) -> None:
        """Keep the answers of people who stay; add new people as PENDING."""
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM agenda_attendees WHERE event_id = %s AND NOT (user_id = ANY(%s))",
                (event_id, people),
            )
            for user_id in people:
                cursor.execute(
                    "INSERT INTO agenda_attendees (id, event_id, user_id) VALUES (%s, %s, %s) "
                    "ON CONFLICT (event_id, user_id) DO NOTHING",
                    (uuid4(), event_id, user_id),
                )

    def cancel_event(self, event_id: UUID) -> None:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                f"UPDATE agenda_events SET cancelled_at = {NOW}, updated_at = {NOW} WHERE id = %s",
                (event_id,),
            )

    def respond(self, event_id: UUID, user_id: UUID, response: str) -> bool:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                f"UPDATE agenda_attendees SET response = %s, responded_at = {NOW} "
                "WHERE event_id = %s AND user_id = %s",
                (response, event_id, user_id),
            )
            return cursor.rowcount == 1

    # -- todos ------------------------------------------------------------------------------

    def todos(
        self,
        company_id: UUID,
        owners: builtins.list[UUID] | None,
        start: date | None = None,
        end: date | None = None,
    ) -> builtins.list[TodoRow]:
        """Open todos and the ones done in the last week; with dates, only those due between."""
        where = "t.company_id = %(company)s"
        if owners is not None:
            where += " AND t.owner_id = ANY(%(owners)s)"
        if start and end:
            where += " AND t.due_date >= %(start)s AND t.due_date < %(end)s"
        else:
            where += f" AND (t.done_at IS NULL OR t.done_at > {NOW} - INTERVAL '7 days')"
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                _TODO + f" WHERE {where} ORDER BY (t.done_at IS NOT NULL), "
                "t.due_date NULLS LAST, t.due_at NULLS LAST, t.created_at LIMIT 1000",
                {"company": company_id, "owners": owners, "start": start, "end": end},
            )
            return [TodoRow(*row) for row in cursor.fetchall()]

    def todo(self, company_id: UUID, todo_id: UUID) -> TodoRow | None:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(_TODO + " WHERE t.company_id = %s AND t.id = %s", (company_id, todo_id))
            row = cursor.fetchone()
            return TodoRow(*row) if row else None

    def create_todo(self, company_id: UUID, owner_id: UUID, fields: dict[str, Any]) -> UUID:
        todo_id = uuid4()
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO agenda_todos (id, company_id, owner_id, title, notes, due_date, "
                "due_at, priority, created_at, updated_at) VALUES (%(id)s, %(company)s, %(owner)s, "
                f"%(title)s, %(notes)s, %(due_date)s, %(due_at)s, %(priority)s, {NOW}, {NOW})",
                {"id": todo_id, "company": company_id, "owner": owner_id, **fields},
            )
        return todo_id

    def update_todo(self, todo_id: UUID, fields: dict[str, Any]) -> None:
        allowed = {"title", "notes", "due_date", "due_at", "priority"}
        sets = [f"{key} = %({key})s" for key in fields if key in allowed]
        if "due_at" in fields:
            sets += ["alerted_before_at = NULL", "alerted_start_at = NULL"]
        if "done" in fields:
            sets.append(f"done_at = CASE WHEN %(done)s THEN {NOW} ELSE NULL END")
        if not sets:
            return
        sets.append(f"updated_at = {NOW}")
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                f"UPDATE agenda_todos SET {', '.join(sets)} WHERE id = %(todo)s",
                {**fields, "todo": todo_id},
            )

    def delete_todo(self, todo_id: UUID) -> None:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute("DELETE FROM agenda_todos WHERE id = %s", (todo_id,))

    # -- other things on the calendar ------------------------------------------------------

    def tasks_due(
        self,
        company_id: UUID,
        start: date,
        end: date,
        people: builtins.list[UUID] | None,
        monitor: UUID | None,
    ) -> builtins.list[TaskDueRow]:
        where = (
            "t.company_id = %(company)s AND t.due_date >= %(start)s AND t.due_date < %(end)s "
            "AND t.status NOT IN ('CANCELLED')"
        )
        if people is not None:
            where += " AND (t.assignee_user_id = ANY(%(people)s)"
            where += " OR t.monitor_user_id = %(monitor)s)" if monitor else ")"
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT t.id, t.number, t.title, t.due_date, t.status::text, t.assignee_user_id, "
                "u.name, c.name FROM tasks t LEFT JOIN users u ON u.id = t.assignee_user_id "
                f"LEFT JOIN clients c ON c.id = t.client_id WHERE {where} "
                "ORDER BY t.due_date, t.number LIMIT 1000",
                {
                    "company": company_id,
                    "start": start,
                    "end": end,
                    "people": people,
                    "monitor": monitor,
                },
            )
            return [TaskDueRow(*row) for row in cursor.fetchall()]

    def meetings(
        self, company_id: UUID, start: datetime, end: datetime, member: UUID | None
    ) -> builtins.list[MeetingDueRow]:
        """Meetings planned in chats (not the ones an event already shows)."""
        where = (
            "m.company_id = %(company)s AND m.cancelled_at IS NULL AND m.starts_at < %(end)s "
            "AND m.starts_at + make_interval(mins => m.duration_minutes) > %(start)s "
            "AND NOT EXISTS (SELECT 1 FROM agenda_events e WHERE e.meeting_id = m.id)"
        )
        if member is not None:
            where += (
                " AND EXISTS (SELECT 1 FROM chat_members cm WHERE cm.conversation_id = "
                "m.conversation_id AND cm.user_id = %(member)s AND cm.is_member)"
            )
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT m.id, m.conversation_id, m.title, m.starts_at, m.duration_minutes, "
                "m.kind::text, COALESCE(NULLIF(c.title, ''), cl.name, 'Direct chat') FROM chat_meetings m "
                "JOIN chat_conversations c ON c.id = m.conversation_id "
                f"LEFT JOIN clients cl ON cl.id = c.client_id WHERE {where} "
                "ORDER BY m.starts_at LIMIT 500",
                {"company": company_id, "start": start, "end": end, "member": member},
            )
            return [MeetingDueRow(*row) for row in cursor.fetchall()]

    # -- alerts -----------------------------------------------------------------------------

    def due_alerts(self, before_minutes: int = 10) -> builtins.list[AlertRow]:
        """Claim the alerts that are due now (each goes out once, even with several workers)."""
        out: builtins.list[AlertRow] = []
        window = f"make_interval(mins => {int(before_minutes)})"
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            for moment, column, condition in (
                (
                    "BEFORE",
                    "alerted_before_at",
                    f"starts_at > {NOW} AND starts_at <= {NOW} + {window}",
                ),
                (
                    "START",
                    "alerted_start_at",
                    f"starts_at <= {NOW} AND starts_at > {NOW} - INTERVAL '5 minutes'",
                ),
            ):
                cursor.execute(
                    f"UPDATE agenda_events e SET {column} = {NOW} WHERE e.cancelled_at IS NULL "
                    f"AND e.all_day = false AND e.{column} IS NULL AND e.{condition} "
                    "RETURNING e.id, e.company_id, e.title, e.starts_at, e.owner_id, e.video, "
                    "e.conversation_id, ARRAY(SELECT a.user_id FROM agenda_attendees a "
                    "WHERE a.event_id = e.id AND a.response <> 'NO')"
                )
                for row in cursor.fetchall():
                    people = list(dict.fromkeys([row[4], *(row[7] or [])]))
                    out.append(
                        AlertRow(
                            "EVENT", moment, row[0], row[1], row[2], row[3], people, row[5], row[6]
                        )
                    )
                due = condition.replace("starts_at", "due_at")
                cursor.execute(
                    f"UPDATE agenda_todos t SET {column} = {NOW} WHERE t.done_at IS NULL "
                    f"AND t.due_at IS NOT NULL AND t.{column} IS NULL AND t.{due} "
                    "RETURNING t.id, t.company_id, t.title, t.due_at, t.owner_id"
                )
                for row in cursor.fetchall():
                    out.append(
                        AlertRow(
                            "TODO", moment, row[0], row[1], row[2], row[3], [row[4]], False, None
                        )
                    )
        return out
