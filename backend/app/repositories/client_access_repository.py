"""Per-client access of managers and employees (owner request 2026-11-26)."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.database.connectivity import database_pool

ACCESS_LEVELS = ("READ", "WRITE", "CREATE")


@dataclass(frozen=True)
class AccessGrant:
    user_id: UUID
    client_id: UUID
    level: str


@dataclass(frozen=True)
class AccessClient:
    id: UUID
    name: str
    code: str


class ClientAccessRepository:
    def levels_for_user(self, company_id: UUID, user_id: UUID) -> dict[UUID, str]:
        """client id -> level, for the active clients this person may work on."""
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT a.client_id, a.level::text FROM client_access a "
                "JOIN clients c ON c.id = a.client_id "
                "WHERE a.company_id = %s AND a.user_id = %s AND c.status = 'ACTIVE'",
                (company_id, user_id),
            )
            return {row[0]: row[1] for row in cursor.fetchall()}

    def my_clients(self, company_id: UUID, user_id: UUID) -> list[tuple[AccessClient, str]]:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT c.id, c.name, COALESCE(c.code, ''), a.level::text FROM client_access a "
                "JOIN clients c ON c.id = a.client_id "
                "WHERE a.company_id = %s AND a.user_id = %s AND c.status = 'ACTIVE' "
                "ORDER BY c.name",
                (company_id, user_id),
            )
            return [(AccessClient(row[0], row[1], row[2]), row[3]) for row in cursor.fetchall()]

    def grants(self, company_id: UUID) -> list[AccessGrant]:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT user_id, client_id, level::text FROM client_access WHERE company_id = %s",
                (company_id,),
            )
            return [AccessGrant(*row) for row in cursor.fetchall()]

    def clients(self, company_id: UUID) -> list[AccessClient]:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, name, COALESCE(code, '') FROM clients "
                "WHERE company_id = %s AND status = 'ACTIVE' ORDER BY name",
                (company_id,),
            )
            return [AccessClient(*row) for row in cursor.fetchall()]

    def set(
        self, company_id: UUID, user_id: UUID, client_id: UUID, level: str | None, actor_id: UUID
    ) -> None:
        """Give, change or (level None) remove one person's access to one client."""
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            if level is None:
                cursor.execute(
                    "DELETE FROM client_access "
                    "WHERE company_id = %s AND user_id = %s AND client_id = %s",
                    (company_id, user_id, client_id),
                )
            else:
                cursor.execute(
                    "INSERT INTO client_access "
                    "(company_id, user_id, client_id, level, granted_by_id, updated_at) "
                    'VALUES (%s, %s, %s, %s::"ClientAccessLevel", %s, NOW()) '
                    "ON CONFLICT (user_id, client_id) DO UPDATE "
                    "SET level = EXCLUDED.level, granted_by_id = EXCLUDED.granted_by_id, "
                    "updated_at = NOW()",
                    (company_id, user_id, client_id, level, actor_id),
                )
            connection.commit()

    def user_ids_for_client(self, company_id: UUID, client_id: UUID) -> list[UUID]:
        """Active managers and employees with any access to this client."""
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT a.user_id FROM client_access a JOIN users u ON u.id = a.user_id "
                "WHERE a.company_id = %s AND a.client_id = %s "
                "AND u.status IN ('ACTIVE', 'PENDING_VERIFICATION')",
                (company_id, client_id),
            )
            return [row[0] for row in cursor.fetchall()]
