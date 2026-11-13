from dataclasses import dataclass
from uuid import UUID, uuid4

from app.database.connectivity import database_pool


@dataclass(frozen=True)
class ProfileDetailsRecord:
    first_name: str | None
    last_name: str | None
    phone_number: str | None
    profile_image_url: str | None
    timezone: str
    language: str
    theme_preference: str
    email_notifications: bool
    password_hash: str


class ProfileRepository:
    def load_details(self, user_id: UUID) -> ProfileDetailsRecord | None:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT first_name,last_name,phone_number,profile_image_url,timezone,language,theme_preference,email_notifications,password_hash FROM users WHERE id=%s",
                    (user_id,),
                )
                record = cursor.fetchone()
                return ProfileDetailsRecord(*record) if record else None

    def update_profile(
        self, user_id: UUID, company_id: UUID | None, values: dict[str, object]
    ) -> bool:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """UPDATE users
                       SET first_name=%s,last_name=%s,phone_number=%s,timezone=%s,
                           language=%s,theme_preference=%s,email_notifications=%s,
                           name=COALESCE(
                               NULLIF(TRIM(CONCAT_WS(' ',%s::text,%s::text)),''),
                               name
                           ),
                           updated_at=NOW()
                       WHERE id=%s AND status='ACTIVE'""",
                    (
                        *values.values(),
                        values["first_name"],
                        values["last_name"],
                        user_id,
                    ),
                )
                if cursor.rowcount != 1:
                    return False
                self._audit(cursor, user_id, company_id, "PROFILE_UPDATED")
                return True

    def change_password(self, user_id: UUID, company_id: UUID | None, password_hash: str) -> bool:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE users SET password_hash=%s,updated_at=NOW() WHERE id=%s AND status='ACTIVE'",
                    (password_hash, user_id),
                )
                if cursor.rowcount != 1:
                    return False
                cursor.execute(
                    "UPDATE auth_sessions SET status='REVOKED',refresh_token_hash=%s,last_activity_at=NOW() WHERE user_id=%s AND status='ACTIVE'",
                    (f"password-change:{uuid4()}", user_id),
                )
                self._audit(cursor, user_id, company_id, "PASSWORD_CHANGED")
                cursor.execute(
                    "INSERT INTO authentication_events (id,event_type,user_id,company_id,details,created_at) "
                    "VALUES (%s,'PASSWORD_CHANGED',%s,%s,%s,NOW())",
                    (uuid4(), user_id, company_id, "Password changed; active sessions revoked"),
                )
                return True

    def update_image(self, user_id: UUID, company_id: UUID | None, url: str) -> bool:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE users SET profile_image_url=%s,updated_at=NOW() WHERE id=%s AND status='ACTIVE'",
                    (url, user_id),
                )
                if cursor.rowcount != 1:
                    return False
                self._audit(cursor, user_id, company_id, "PROFILE_IMAGE_UPDATED")
                return True

    @staticmethod
    def _audit(cursor: object, user_id: UUID, company_id: UUID | None, action: str) -> None:
        cursor.execute(  # type: ignore[attr-defined]
            "INSERT INTO profile_audits (id,user_id,company_id,action,created_at) VALUES (%s,%s,%s,%s,NOW())",
            (uuid4(), user_id, company_id, action),
        )

    def foundation_is_ready(self) -> bool:
        try:
            with database_pool.connection(timeout=2) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT to_regclass('public.profile_audits') IS NOT NULL")
                    record = cursor.fetchone()
                    return bool(record and record[0])
        except Exception:
            return False
