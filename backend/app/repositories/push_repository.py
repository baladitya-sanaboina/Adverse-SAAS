"""Web Push subscriptions (owner request 2026-11-15)."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from app.database.connectivity import database_pool


@dataclass(frozen=True)
class SubscriptionRow:
    id: UUID
    user_id: UUID
    endpoint: str
    p256dh: str
    auth: str


class PushRepository:
    def save(self, user_id: UUID, endpoint: str, p256dh: str, auth: str, agent: str) -> None:
        """One row per browser; signing in as someone else on it moves it to them."""
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO push_subscriptions (id, user_id, endpoint, p256dh, auth, user_agent, "
                "created_at) VALUES (%s, %s, %s, %s, %s, %s, NOW() AT TIME ZONE 'UTC') "
                "ON CONFLICT (endpoint) DO UPDATE SET user_id = EXCLUDED.user_id, "
                "p256dh = EXCLUDED.p256dh, auth = EXCLUDED.auth, "
                "user_agent = EXCLUDED.user_agent, failures = 0",
                (uuid4(), user_id, endpoint, p256dh, auth, agent[:300]),
            )

    def remove(self, user_id: UUID, endpoint: str) -> None:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM push_subscriptions WHERE user_id = %s AND endpoint = %s",
                (user_id, endpoint),
            )

    def for_users(self, user_ids: list[UUID]) -> list[SubscriptionRow]:
        if not user_ids:
            return []
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, user_id, endpoint, p256dh, auth FROM push_subscriptions "
                "WHERE user_id = ANY(%s)",
                (user_ids,),
            )
            return [SubscriptionRow(*row) for row in cursor.fetchall()]

    def sent(self, subscription_id: UUID) -> None:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "UPDATE push_subscriptions SET last_sent_at = NOW() AT TIME ZONE 'UTC', "
                "failures = 0 WHERE id = %s",
                (subscription_id,),
            )

    def failed(self, subscription_id: UUID, gone: bool) -> None:
        """A browser that unsubscribed (404/410) or keeps failing is dropped."""
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            if gone:
                cursor.execute("DELETE FROM push_subscriptions WHERE id = %s", (subscription_id,))
                return
            cursor.execute(
                "UPDATE push_subscriptions SET failures = failures + 1 WHERE id = %s "
                "RETURNING failures",
                (subscription_id,),
            )
            row = cursor.fetchone()
            if row and int(row[0]) >= 10:
                cursor.execute("DELETE FROM push_subscriptions WHERE id = %s", (subscription_id,))
