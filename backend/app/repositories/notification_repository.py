"""Storage for in-app notifications (Phase 10)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from app.database.connectivity import database_pool


@dataclass(frozen=True)
class NotificationRow:
    id: UUID
    type: str
    title: str
    body: str
    link: str
    data: dict[str, Any]
    read_at: datetime | None
    created_at: datetime


_COLUMNS = "id, type, title, body, link, data, read_at, created_at"


class NotificationRepository:
    def insert_many(
        self,
        company_id: UUID,
        user_ids: list[UUID],
        type_: str,
        title: str,
        body: str,
        link: str,
        data: dict[str, Any],
    ) -> dict[UUID, NotificationRow]:
        """One row per recipient; returns the stored row for each recipient."""
        stored: dict[UUID, NotificationRow] = {}
        if not user_ids:
            return stored
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            for user_id in user_ids:
                cursor.execute(
                    f"""
                    INSERT INTO notifications (id, company_id, user_id, type, title, body, link, data)
                    SELECT %s, %s, u.id, %s, %s, %s, %s, %s::jsonb
                    FROM users u WHERE u.id = %s AND u.company_id = %s
                    RETURNING {_COLUMNS}
                    """,
                    (
                        uuid4(),
                        company_id,
                        type_,
                        title[:200],
                        body[:500],
                        link[:300],
                        json.dumps(data, default=str),
                        user_id,
                        company_id,
                    ),
                )
                row = cursor.fetchone()
                if row:
                    stored[user_id] = NotificationRow(*row)
        return stored

    def list_for_user(
        self,
        company_id: UUID,
        user_id: UUID,
        limit: int,
        before: datetime | None,
        unread_only: bool,
    ) -> list[NotificationRow]:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT {_COLUMNS} FROM notifications
                WHERE company_id=%(company)s AND user_id=%(user)s
                  AND (%(before)s::timestamp IS NULL OR created_at < %(before)s::timestamp)
                  AND (NOT %(unread)s OR read_at IS NULL)
                ORDER BY created_at DESC, id DESC
                LIMIT %(limit)s
                """,
                {
                    "company": company_id,
                    "user": user_id,
                    "before": before,
                    "unread": unread_only,
                    "limit": limit,
                },
            )
            return [NotificationRow(*row) for row in cursor.fetchall()]

    def unread_count(self, company_id: UUID, user_id: UUID) -> int:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM notifications WHERE company_id=%s AND user_id=%s AND read_at IS NULL",
                (company_id, user_id),
            )
            row = cursor.fetchone()
            return int(row[0]) if row else 0

    def mark_read(self, company_id: UUID, user_id: UUID, notification_id: UUID | None) -> int:
        """Mark one notification (or all when `notification_id` is None) as read."""
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE notifications SET read_at = NOW() AT TIME ZONE 'UTC'
                WHERE company_id=%s AND user_id=%s AND read_at IS NULL
                  AND (%s::uuid IS NULL OR id = %s::uuid)
                """,
                (company_id, user_id, notification_id, notification_id),
            )
            return int(cursor.rowcount or 0)

    def company_admin_ids(self, company_id: UUID) -> list[UUID]:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT u.id FROM users u JOIN roles r ON r.id = u.role_id
                WHERE u.company_id=%s AND r.code='COMPANY_ADMIN' AND u.status='ACTIVE'
                """,
                (company_id,),
            )
            return [row[0] for row in cursor.fetchall()]

    def client_user_id(self, company_id: UUID, client_id: UUID) -> UUID | None:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT user_id FROM clients WHERE company_id=%s AND id=%s AND user_id IS NOT NULL",
                (company_id, client_id),
            )
            row = cursor.fetchone()
            return row[0] if row else None
