from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from app.database.connectivity import database_pool


@dataclass(frozen=True)
class AuthenticationUserRecord:
    id: UUID
    name: str
    email: str
    password_hash: str
    status: str
    role: str
    role_status: str
    company_id: UUID | None
    company_name: str | None
    company_code: str | None
    company_status: str | None
    failed_login_attempts: int
    locked_until: datetime | None


@dataclass(frozen=True)
class LoginProtectionRecord:
    failed_attempts: int
    locked_until: datetime | None


class AuthenticationRepository:
    @staticmethod
    def _user_query(where_clause: str) -> str:
        return (
            "SELECT u.id, u.name, u.email, u.password_hash, u.status::text, r.code, r.status::text, "
            'u.company_id, c.name, c.code, c.status::text, u.failed_login_attempts, u.locked_until FROM "users" u '
            'JOIN "roles" r ON r.id = u.role_id '
            'LEFT JOIN "companies" c ON c.id = u.company_id '
            f"WHERE {where_clause}"
        )

    def find_user_by_email(self, email: str) -> AuthenticationUserRecord | None:
        """By login email. A client may also sign in with their own Gmail (owner request
        2026-11-19); that is used only when it belongs to exactly one client account."""
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    self._user_query("LOWER(u.email) = LOWER(%s)"),
                    (email,),
                )
                record = cursor.fetchone()
                if record:
                    return AuthenticationUserRecord(*record)
                cursor.execute(
                    self._user_query(
                        "LOWER(u.recovery_email) = LOWER(%s) AND r.code = 'COMPANY_CLIENT' LIMIT 2"
                    ),
                    (email,),
                )
                found = cursor.fetchall()
                return AuthenticationUserRecord(*found[0]) if len(found) == 1 else None

    def find_user_by_id(self, user_id: UUID) -> AuthenticationUserRecord | None:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(self._user_query("u.id = %s"), (user_id,))
                record = cursor.fetchone()
                return AuthenticationUserRecord(*record) if record else None

    def create_session(
        self,
        user_id: UUID,
        company_id: UUID | None,
        refresh_hash: str,
        expires_at: datetime,
        device_info: str | None,
    ) -> UUID:
        session_id = uuid4()
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    'INSERT INTO "auth_sessions" '
                    "(id, user_id, company_id, refresh_token_hash, status, login_at, last_activity_at, expires_at, device_info) "
                    "VALUES (%s, %s, %s, %s, 'ACTIVE', NOW(), NOW(), %s, %s)",
                    (session_id, user_id, company_id, refresh_hash, expires_at, device_info),
                )
        return session_id

    def record_failed_login(
        self, user_id: UUID, maximum_attempts: int, lock_duration: datetime
    ) -> LoginProtectionRecord:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    'UPDATE "users" SET failed_login_attempts = failed_login_attempts + 1, '
                    "locked_until = CASE WHEN failed_login_attempts + 1 >= %s THEN %s ELSE locked_until END, "
                    "updated_at = NOW() WHERE id = %s "
                    "RETURNING failed_login_attempts, locked_until",
                    (maximum_attempts, lock_duration, user_id),
                )
                record = cursor.fetchone()
                if record is None:
                    raise RuntimeError("Failed login counter user does not exist.")
                return LoginProtectionRecord(*record)

    def clear_login_protection(self, user_id: UUID) -> None:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    'UPDATE "users" SET failed_login_attempts = 0, locked_until = NULL, updated_at = NOW() '
                    "WHERE id = %s AND (failed_login_attempts <> 0 OR locked_until IS NOT NULL)",
                    (user_id,),
                )

    def update_password_hash(self, user_id: UUID, password_hash: str) -> None:
        """Store a stronger hash of the same password (made right after a correct sign-in)."""
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    'UPDATE "users" SET password_hash = %s, updated_at = NOW() WHERE id = %s',
                    (password_hash, user_id),
                )

    def recent_failed_logins(self, email: str, ip_address: str | None, since: datetime) -> int:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    'SELECT COUNT(*) FROM "authentication_events" '
                    "WHERE event_type = 'LOGIN_FAILED' AND LOWER(email) = LOWER(%s) "
                    "AND ip_address IS NOT DISTINCT FROM %s AND created_at >= %s",
                    (email, ip_address, since),
                )
                record = cursor.fetchone()
                return int(record[0]) if record else 0

    def set_refresh_hash(self, session_id: UUID, refresh_hash: str) -> None:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    'UPDATE "auth_sessions" SET refresh_token_hash = %s WHERE id = %s',
                    (refresh_hash, session_id),
                )

    def session_is_active(self, session_id: UUID, user_id: UUID) -> bool:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    'SELECT EXISTS (SELECT 1 FROM "auth_sessions" WHERE id = %s AND user_id = %s '
                    "AND status = 'ACTIVE' AND expires_at > NOW())",
                    (session_id, user_id),
                )
                record = cursor.fetchone()
                return bool(record and record[0])

    def refresh_matches(self, session_id: UUID, user_id: UUID, refresh_hash: str) -> bool:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    'SELECT EXISTS (SELECT 1 FROM "auth_sessions" WHERE id = %s AND user_id = %s '
                    "AND refresh_token_hash = %s AND status = 'ACTIVE' AND expires_at > NOW())",
                    (session_id, user_id, refresh_hash),
                )
                record = cursor.fetchone()
                return bool(record and record[0])

    def rotate_refresh_token(
        self, session_id: UUID, user_id: UUID, current_hash: str, new_hash: str
    ) -> bool:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    'UPDATE "auth_sessions" SET refresh_token_hash = %s, last_activity_at = NOW() '
                    "WHERE id = %s AND user_id = %s AND refresh_token_hash = %s AND status = 'ACTIVE' "
                    "AND expires_at > NOW()",
                    (new_hash, session_id, user_id, current_hash),
                )
                return cursor.rowcount == 1

    def revoke_session(self, session_id: UUID, user_id: UUID) -> bool:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE \"auth_sessions\" SET status = 'REVOKED', "
                    "refresh_token_hash = %s, last_activity_at = NOW() "
                    "WHERE id = %s AND user_id = %s AND status = 'ACTIVE'",
                    (f"revoked:{uuid4()}", session_id, user_id),
                )
                return cursor.rowcount == 1

    def expire_session(self, session_id: UUID) -> bool:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE \"auth_sessions\" SET status = 'EXPIRED' "
                    "WHERE id = %s AND status = 'ACTIVE' AND expires_at <= NOW()",
                    (session_id,),
                )
                return cursor.rowcount == 1

    def log_event(
        self,
        event_type: str,
        *,
        user_id: UUID | None = None,
        session_id: UUID | None = None,
        email: str | None = None,
        details: str | None = None,
        company_id: UUID | None = None,
        ip_address: str | None = None,
    ) -> None:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    'INSERT INTO "authentication_events" '
                    "(id, event_type, user_id, session_id, email, details, company_id, ip_address, created_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())",
                    (
                        uuid4(),
                        event_type,
                        user_id,
                        session_id,
                        email,
                        details,
                        company_id,
                        ip_address,
                    ),
                )

    def touch_session(self, session_id: UUID) -> None:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    'UPDATE "auth_sessions" SET last_activity_at = NOW() WHERE id = %s',
                    (session_id,),
                )

    def foundation_is_ready(self) -> bool:
        try:
            with database_pool.connection(timeout=2) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT to_regclass('public.auth_sessions') IS NOT NULL "
                        "AND to_regclass('public.authentication_events') IS NOT NULL"
                    )
                    record = cursor.fetchone()
                    return bool(record and record[0])
        except Exception:
            return False
