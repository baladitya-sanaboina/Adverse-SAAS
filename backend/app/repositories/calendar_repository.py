"""Storage for the content calendar (Phase 13)."""

from __future__ import annotations

import builtins
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

from app.database.connectivity import database_pool


@dataclass(frozen=True)
class CalendarEntryRow:
    id: UUID
    client_id: UUID
    client_name: str
    client_code: str
    entry_date: date
    title: str
    reference_url: str
    notes: str
    no_post: bool
    recorded: bool
    script_ready: bool
    posted_instagram: bool
    posted_youtube: bool
    edited_manual: bool
    script_file_name: str | None
    script_storage_path: str | None
    script_mime_type: str | None
    script_size_bytes: int | None
    task_id: UUID | None
    task_number: int | None
    task_title: str | None
    task_status: str | None
    created_by_name: str
    created_at: datetime
    updated_at: datetime
    script_url: str = ""
    pdf_url: str = ""
    service_id: UUID | None = None
    service_name: str | None = None
    # Added by a manager or employee (owner request 2026-11-26: shown in another colour).
    added_by_team: bool = False


_SELECT = """
SELECT e.id, e.client_id, c.name, c.code, e.entry_date, e.title, e.reference_url, e.notes,
  e.no_post, e.recorded, e.script_ready, e.posted_instagram, e.posted_youtube, e.edited_manual,
  e.script_file_name, e.script_storage_path, e.script_mime_type, e.script_size_bytes,
  e.task_id, t.number, t.title, t.status::text,
  COALESCE(NULLIF(TRIM(CONCAT(u.first_name, ' ', u.last_name)), ''), u.email, ''),
  e.created_at, e.updated_at, e.script_url, e.pdf_url, e.service_id, sv.name,
  COALESCE(ur.code IN ('COMPANY_MANAGER', 'COMPANY_EMPLOYEE'), FALSE)
FROM content_calendar_entries e
JOIN clients c ON c.id = e.client_id
LEFT JOIN company_services sv ON sv.id = e.service_id
LEFT JOIN tasks t ON t.id = e.task_id
LEFT JOIN users u ON u.id = e.created_by_id
LEFT JOIN roles ur ON ur.id = u.role_id
"""

# Columns a caller may change through update(); anything else is ignored.
EDITABLE = (
    "service_id",
    "entry_date",
    "title",
    "reference_url",
    "script_url",
    "pdf_url",
    "notes",
    "no_post",
    "recorded",
    "script_ready",
    "posted_instagram",
    "posted_youtube",
    "edited_manual",
)


def _row(row: tuple[Any, ...]) -> CalendarEntryRow:
    values = list(row)
    values[17] = int(values[17]) if values[17] is not None else None  # BIGINT size
    return CalendarEntryRow(*values)


class CalendarRepository:
    def list(
        self,
        company_id: UUID,
        client_id: UUID | None,
        start: date | None,
        end: date | None,
        client_ids: list[UUID] | None = None,
    ) -> list[CalendarEntryRow]:
        """`client_ids`: only these clients (a manager's or employee's clients)."""
        where = ["e.company_id = %(company)s"]
        if client_id is not None:
            where.append("e.client_id = %(client)s")
        if client_ids is not None:
            where.append("e.client_id = ANY(%(clients)s)")
        if start is not None:
            where.append("e.entry_date >= %(start)s")
        if end is not None:
            where.append("e.entry_date <= %(end)s")
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                _SELECT + " WHERE " + " AND ".join(where) + " ORDER BY e.entry_date, e.created_at",
                {
                    "company": company_id,
                    "client": client_id,
                    "clients": client_ids or [],
                    "start": start,
                    "end": end,
                },
            )
            return [_row(row) for row in cursor.fetchall()]

    def get(self, company_id: UUID, entry_id: UUID) -> CalendarEntryRow | None:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                _SELECT + " WHERE e.company_id = %s AND e.id = %s", (company_id, entry_id)
            )
            row = cursor.fetchone()
            return _row(row) if row else None

    def create(
        self,
        company_id: UUID,
        client_id: UUID,
        actor_id: UUID,
        values: dict[str, Any],
    ) -> UUID:
        entry_id = uuid4()
        columns = [name for name in EDITABLE if name in values]
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO content_calendar_entries (id, company_id, client_id, created_by_id, "
                + ", ".join(columns)
                + ", updated_at) VALUES (%s, %s, %s, %s, "
                + ", ".join(["%s"] * len(columns))
                + ", CURRENT_TIMESTAMP)",
                (entry_id, company_id, client_id, actor_id, *[values[name] for name in columns]),
            )
            connection.commit()
        return entry_id

    def update(self, company_id: UUID, entry_id: UUID, values: dict[str, Any]) -> None:
        columns = [name for name in EDITABLE if name in values]
        if not columns:
            return
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "UPDATE content_calendar_entries SET "
                + ", ".join(f"{name} = %s" for name in columns)
                + ", updated_at = CURRENT_TIMESTAMP WHERE company_id = %s AND id = %s",
                (*[values[name] for name in columns], company_id, entry_id),
            )
            connection.commit()

    def set_task(self, company_id: UUID, entry_id: UUID, task_id: UUID | None) -> None:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "UPDATE content_calendar_entries SET task_id = %s, updated_at = CURRENT_TIMESTAMP "
                "WHERE company_id = %s AND id = %s",
                (task_id, company_id, entry_id),
            )
            connection.commit()

    def set_script(
        self,
        company_id: UUID,
        entry_id: UUID,
        name: str | None,
        path: str | None,
        mime: str | None,
        size: int | None,
    ) -> None:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "UPDATE content_calendar_entries SET script_file_name = %s, "
                "script_storage_path = %s, script_mime_type = %s, script_size_bytes = %s, "
                "updated_at = CURRENT_TIMESTAMP WHERE company_id = %s AND id = %s",
                (name, path, mime, size, company_id, entry_id),
            )
            connection.commit()

    def delete(self, company_id: UUID, entry_id: UUID) -> bool:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM content_calendar_entries WHERE company_id = %s AND id = %s",
                (company_id, entry_id),
            )
            deleted = cursor.rowcount > 0
            connection.commit()
        return deleted

    def task_client(self, company_id: UUID, task_id: UUID) -> UUID | None:
        """The client a task belongs to, so an entry is only linked to its own client's task."""
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT client_id FROM tasks WHERE company_id = %s AND id = %s",
                (company_id, task_id),
            )
            row = cursor.fetchone()
            return row[0] if row else None

    # -- staff calendar (owner request 2026-11-14: a calendar in every role) -------------------

    def staff_tasks(
        self, company_id: UUID, user_id: UUID, start: date, end: date
    ) -> builtins.list[tuple[Any, ...]]:
        """My tasks (assigned or monitoring) due in the range: no prices."""
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT t.id, t.number, t.title, t.status::text, t.due_date, c.name,
                  CASE WHEN t.assignee_user_id = %(user)s THEN 'ASSIGNEE' ELSE 'MONITOR' END
                FROM tasks t JOIN clients c ON c.id = t.client_id
                WHERE t.company_id = %(company)s
                  AND (t.assignee_user_id = %(user)s OR t.monitor_user_id = %(user)s)
                  AND t.status::text <> 'CANCELLED'
                  AND t.due_date BETWEEN %(start)s AND %(end)s
                ORDER BY t.due_date, t.number
                """,
                {"company": company_id, "user": user_id, "start": start, "end": end},
            )
            return list(cursor.fetchall())

    def staff_entries(
        self, company_id: UUID, user_id: UUID, start: date, end: date
    ) -> builtins.list[CalendarEntryRow]:
        """Content calendar entries whose ticket is mine (assigned or monitoring)."""
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                _SELECT
                + """ WHERE e.company_id = %(company)s
                  AND e.entry_date BETWEEN %(start)s AND %(end)s
                  AND (t.assignee_user_id = %(user)s OR t.monitor_user_id = %(user)s)
                ORDER BY e.entry_date, e.created_at""",
                {"company": company_id, "user": user_id, "start": start, "end": end},
            )
            return [_row(row) for row in cursor.fetchall()]
