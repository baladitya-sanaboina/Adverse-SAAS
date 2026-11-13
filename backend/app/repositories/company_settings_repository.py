from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from psycopg.errors import UniqueViolation
from psycopg.types.json import Jsonb

from app.database.connectivity import database_pool


@dataclass(frozen=True)
class CompanySettingsRecord:
    company_id: str
    company_code: str
    company_name: str
    description: str | None
    business_email: str | None
    phone: str | None
    address: str | None
    website: str | None
    timezone: str
    language: str
    logo_url: str | None
    favicon_url: str | None
    primary_color: str
    secondary_color: str
    email_footer: str
    support_email: str | None
    support_phone: str | None
    gst_tax_id: str | None
    registration_number: str | None
    currency: str
    date_format: str
    time_format: str
    working_days: list[str]
    business_hours: dict[str, str]
    theme: str
    notifications: dict[str, bool]
    updated_at: datetime
    accent_color: str = "#0876ED"
    info_color: str = "#2563A6"
    success_color: str = "#16855B"
    warning_color: str = "#B7791F"
    danger_color: str = "#C2414F"


class CompanySettingsRepository:
    _select = """SELECT c.id::text,c.code,c.name,c.description,c.contact_email,c.phone,c.address,c.website,
      c.timezone,c.language,d.logo_url,d.favicon_url,d.primary_color,d.secondary_color,
      d.email_footer,d.support_email,d.support_phone,d.gst_tax_id,d.registration_number,
      d.currency,d.date_format,d.time_format,d.working_days,d.business_hours,d.theme,
      d.notification_preferences,d.updated_at,d.accent_color,d.info_color,d.success_color,
      d.warning_color,d.danger_color
      FROM companies c JOIN company_tenant_defaults d ON d.company_id=c.id
      WHERE c.id=%s"""

    @staticmethod
    def _record(row: tuple[Any, ...]) -> CompanySettingsRecord:
        return CompanySettingsRecord(
            company_id=row[0],
            company_code=row[1],
            company_name=row[2],
            description=row[3],
            business_email=row[4],
            phone=row[5],
            address=row[6],
            website=row[7],
            timezone=row[8],
            language=row[9],
            logo_url=row[10],
            favicon_url=row[11],
            primary_color=row[12],
            secondary_color=row[13],
            email_footer=row[14],
            support_email=row[15],
            support_phone=row[16],
            gst_tax_id=row[17],
            registration_number=row[18],
            currency=row[19],
            date_format=row[20],
            time_format=row[21],
            working_days=list(row[22]),
            business_hours=dict(row[23]),
            theme=row[24],
            notifications=dict(row[25]),
            updated_at=row[26],
            accent_color=row[27],
            info_color=row[28],
            success_color=row[29],
            warning_color=row[30],
            danger_color=row[31],
        )

    def get(self, company_id: UUID) -> CompanySettingsRecord | None:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(self._select, (company_id,))
                row = cursor.fetchone()
                return self._record(row) if row else None

    def update(
        self,
        actor_id: UUID,
        company_id: UUID,
        company_values: dict[str, Any],
        default_values: dict[str, Any],
        actions: list[str],
    ) -> CompanySettingsRecord | None:
        changed = list(company_values) + list(default_values)
        try:
            with database_pool.connection(timeout=2) as connection:
                with connection.cursor() as cursor:
                    if company_values:
                        setters = ",".join(f"{key}=%s" for key in company_values)
                        cursor.execute(
                            f"UPDATE companies SET {setters},updated_at=NOW() WHERE id=%s",
                            (*company_values.values(), company_id),
                        )
                    if default_values:
                        values = {
                            key: Jsonb(value) if isinstance(value, dict) else value
                            for key, value in default_values.items()
                        }
                        setters = ",".join(f"{key}=%s" for key in values)
                        cursor.execute(
                            f"UPDATE company_tenant_defaults SET {setters},updated_at=NOW() WHERE company_id=%s",
                            (*values.values(), company_id),
                        )
                    for action in actions:
                        cursor.execute(
                            """INSERT INTO company_setting_audits(id,actor_id,company_id,action,details)
                            VALUES(%s,%s,%s,%s,%s)""",
                            (
                                uuid4(),
                                actor_id,
                                company_id,
                                action,
                                Jsonb({"changed_fields": changed}),
                            ),
                        )
        except UniqueViolation as error:
            raise ValueError("Company name or business email is already in use.") from error
        return self.get(company_id)

    def is_ready(self) -> bool:
        try:
            with database_pool.connection(timeout=2) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT to_regclass('public.company_setting_audits') IS NOT NULL"
                    )
                    row = cursor.fetchone()
                    return bool(row and row[0])
        except Exception:
            return False
