from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from app.database.connectivity import database_pool


@dataclass(frozen=True)
class RecoveryUserRecord:
    id: UUID
    email: str
    status: str
    role: str


@dataclass(frozen=True)
class PasswordResetRecord:
    id: UUID
    user_id: UUID
    expires_at: datetime
    used_at: datetime | None
    user_status: str


class PasswordRecoveryRepository:
    def find_user_by_email(self, email: str) -> RecoveryUserRecord | None:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    'SELECT u.id, u.email, u.status::text, r.code FROM "users" u '
                    'JOIN "roles" r ON r.id = u.role_id WHERE LOWER(u.email) = LOWER(%s)',
                    (email,),
                )
                record = cursor.fetchone()
                return RecoveryUserRecord(*record) if record else None

    def create_reset_token(self, user_id: UUID, token_hash: str, expires_at: datetime) -> None:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    'DELETE FROM "password_reset_tokens" WHERE user_id = %s AND used_at IS NULL',
                    (user_id,),
                )
                cursor.execute(
                    'INSERT INTO "password_reset_tokens" '
                    "(id, user_id, token_hash, expires_at, created_at) "
                    "VALUES (%s, %s, %s, %s, NOW())",
                    (uuid4(), user_id, token_hash, expires_at),
                )

    def find_reset_token(self, token_hash: str) -> PasswordResetRecord | None:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT t.id, t.user_id, t.expires_at, t.used_at, u.status::text "
                    'FROM "password_reset_tokens" t JOIN "users" u ON u.id = t.user_id '
                    "WHERE t.token_hash = %s",
                    (token_hash,),
                )
                record = cursor.fetchone()
                return PasswordResetRecord(*record) if record else None

    def consume_reset_token(self, token_id: UUID, user_id: UUID, password_hash: str) -> bool:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    'UPDATE "password_reset_tokens" SET used_at = NOW() '
                    "WHERE id = %s AND user_id = %s AND used_at IS NULL AND expires_at > NOW()",
                    (token_id, user_id),
                )
                if cursor.rowcount != 1:
                    return False
                cursor.execute(
                    'UPDATE "users" SET password_hash = %s, updated_at = NOW() '
                    "WHERE id = %s AND status = 'ACTIVE'",
                    (password_hash, user_id),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError("Active reset user was not updated.")
                cursor.execute(
                    "SELECT id FROM \"auth_sessions\" WHERE user_id = %s AND status = 'ACTIVE' "
                    "FOR UPDATE",
                    (user_id,),
                )
                session_ids = [record[0] for record in cursor.fetchall()]
                cursor.execute(
                    "UPDATE \"auth_sessions\" SET status = 'REVOKED', "
                    "refresh_token_hash = %s, last_activity_at = NOW() "
                    "WHERE user_id = %s AND status = 'ACTIVE'",
                    (f"password-reset:{uuid4()}", user_id),
                )
                for session_id in session_ids:
                    cursor.execute(
                        'INSERT INTO "authentication_events" '
                        "(id, event_type, user_id, session_id, details, created_at) "
                        "VALUES (%s, 'TOKEN_REVOKED', %s, %s, %s, NOW())",
                        (
                            uuid4(),
                            user_id,
                            session_id,
                            "Session revoked after password reset",
                        ),
                    )
                cursor.execute(
                    'INSERT INTO "authentication_events" '
                    "(id, event_type, user_id, company_id, details, created_at) "
                    "SELECT %s, 'PASSWORD_RESET', id, company_id, %s, NOW() FROM users WHERE id = %s",
                    (uuid4(), "Password reset completed; active sessions revoked", user_id),
                )
                return True

    def foundation_is_ready(self) -> bool:
        try:
            with database_pool.connection(timeout=2) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT to_regclass('public.password_reset_tokens') IS NOT NULL")
                    record = cursor.fetchone()
                    return bool(record and record[0])
        except Exception:
            return False
