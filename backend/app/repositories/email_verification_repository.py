from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from app.database.connectivity import database_pool


@dataclass(frozen=True)
class VerificationUserRecord:
    id: UUID
    email: str
    status: str
    role: str


@dataclass(frozen=True)
class VerificationTokenRecord:
    id: UUID
    user_id: UUID
    expires_at: datetime
    user_status: str


class EmailVerificationRepository:
    def find_user_by_email(self, email: str) -> VerificationUserRecord | None:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    'SELECT u.id, u.email, u.status::text, r.code FROM "users" u '
                    'JOIN "roles" r ON r.id = u.role_id WHERE LOWER(u.email) = LOWER(%s)',
                    (email,),
                )
                record = cursor.fetchone()
                return VerificationUserRecord(*record) if record else None

    def create_token(self, user_id: UUID, token_hash: str, expires_at: datetime) -> None:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    'DELETE FROM "email_verification_tokens" WHERE user_id = %s', (user_id,)
                )
                cursor.execute(
                    'INSERT INTO "email_verification_tokens" '
                    "(id, user_id, token_hash, expires_at, created_at) VALUES (%s, %s, %s, %s, NOW())",
                    (uuid4(), user_id, token_hash, expires_at),
                )

    def seconds_since_latest(self, user_id: UUID) -> float | None:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT EXTRACT(EPOCH FROM (NOW() - created_at)) "
                    'FROM "email_verification_tokens" WHERE user_id = %s ORDER BY created_at DESC LIMIT 1',
                    (user_id,),
                )
                record = cursor.fetchone()
                return float(record[0]) if record else None

    def use_attempt(self, user_id: UUID) -> int | None:
        """Count one check of the user's open verification code before it is compared.

        Returns how many checks the code has had, or None when the user has no open code.
        """
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    'UPDATE "email_verification_tokens" SET attempts = attempts + 1 '
                    "WHERE user_id = %s AND expires_at > NOW() RETURNING attempts",
                    (user_id,),
                )
                record = cursor.fetchone()
                return int(record[0]) if record else None

    def find_token(self, token_hash: str) -> VerificationTokenRecord | None:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT t.id, t.user_id, t.expires_at, u.status::text "
                    'FROM "email_verification_tokens" t JOIN "users" u ON u.id = t.user_id '
                    "WHERE t.token_hash = %s",
                    (token_hash,),
                )
                record = cursor.fetchone()
                return VerificationTokenRecord(*record) if record else None

    def activate_user(self, token_id: UUID, user_id: UUID) -> bool:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    'DELETE FROM "email_verification_tokens" '
                    "WHERE id = %s AND user_id = %s AND expires_at > NOW() RETURNING id",
                    (token_id, user_id),
                )
                if cursor.fetchone() is None:
                    return False
                cursor.execute(
                    "UPDATE \"users\" SET status = 'ACTIVE', updated_at = NOW() "
                    "WHERE id = %s AND status = 'PENDING_VERIFICATION' RETURNING company_id, email",
                    (user_id,),
                )
                user = cursor.fetchone()
                if user is None:
                    return False
                cursor.execute(
                    'INSERT INTO "authentication_events" '
                    "(id, event_type, user_id, company_id, email, details, created_at) "
                    "VALUES (%s, 'EMAIL_VERIFIED', %s, %s, %s, %s, NOW())",
                    (uuid4(), user_id, user[0], user[1], "Email verified and account activated"),
                )
                return True

    def foundation_is_ready(self) -> bool:
        try:
            with database_pool.connection(timeout=2) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT to_regclass('public.email_verification_tokens') IS NOT NULL"
                    )
                    record = cursor.fetchone()
                    return bool(record and record[0])
        except Exception:
            return False
