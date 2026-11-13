from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from app.database.connectivity import database_pool


@dataclass(frozen=True)
class PlatformSettingsRecord:
    id: str
    platform_name: str
    platform_logo_url: str | None
    favicon_url: str | None
    primary_color: str
    secondary_color: str
    footer_text: str
    support_email: str
    support_phone: str | None
    default_timezone: str
    default_language: str
    default_company_status: str
    default_user_status: str
    default_subscription_code: str
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password_encrypted: str
    smtp_encryption: str
    smtp_sender_name: str
    smtp_sender_email: str
    maintenance_enabled: bool
    maintenance_message: str
    maintenance_allowed_roles: list[str]
    created_at: datetime
    updated_at: datetime


class PlatformSettingsRepository:
    _columns = """id,platform_name,platform_logo_url,favicon_url,primary_color,
        secondary_color,footer_text,support_email,support_phone,default_timezone,
        default_language,default_company_status,default_user_status,
        default_subscription_code,smtp_host,smtp_port,smtp_username,
        smtp_password_encrypted,smtp_encryption,smtp_sender_name,smtp_sender_email,
        maintenance_enabled,maintenance_message,maintenance_allowed_roles,
        created_at,updated_at"""

    @staticmethod
    def _record(row: tuple[Any, ...]) -> PlatformSettingsRecord:
        return PlatformSettingsRecord(
            id=row[0],
            platform_name=row[1],
            platform_logo_url=row[2],
            favicon_url=row[3],
            primary_color=row[4],
            secondary_color=row[5],
            footer_text=row[6],
            support_email=row[7],
            support_phone=row[8],
            default_timezone=row[9],
            default_language=row[10],
            default_company_status=row[11],
            default_user_status=row[12],
            default_subscription_code=row[13],
            smtp_host=row[14],
            smtp_port=row[15],
            smtp_username=row[16],
            smtp_password_encrypted=row[17],
            smtp_encryption=row[18],
            smtp_sender_name=row[19],
            smtp_sender_email=row[20],
            maintenance_enabled=row[21],
            maintenance_message=row[22],
            maintenance_allowed_roles=list(row[23]),
            created_at=row[24],
            updated_at=row[25],
        )

    def get(self) -> PlatformSettingsRecord:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(f"SELECT {self._columns} FROM platform_settings WHERE id='global'")
                row = cursor.fetchone()
                if not row:
                    raise RuntimeError("Global platform settings are not initialized.")
                return self._record(row)

    def update(self, actor_id: UUID, values: dict[str, Any], action: str) -> PlatformSettingsRecord:
        if not values:
            return self.get()
        current = self.get()
        previous = {key: getattr(current, key) for key in values}
        columns = ",".join(f"{key}=%s" for key in values)
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"UPDATE platform_settings SET {columns},updated_at=NOW() WHERE id='global'",
                    tuple(values.values()),
                )
                cursor.execute(
                    """INSERT INTO platform_setting_audits
                    (id,actor_id,action,changed_fields,previous_value,new_value)
                    VALUES(%s,%s,%s,%s,%s,%s)""",
                    (
                        uuid4(),
                        actor_id,
                        action,
                        list(values),
                        Jsonb(previous),
                        Jsonb(values),
                    ),
                )
        return self.get()

    def audit(self, actor_id: UUID, action: str) -> None:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO platform_setting_audits
                    (id,actor_id,action,changed_fields) VALUES(%s,%s,%s,%s)""",
                    (uuid4(), actor_id, action, []),
                )

    def is_ready(self) -> bool:
        try:
            return self.get().id == "global"
        except Exception:
            return False
