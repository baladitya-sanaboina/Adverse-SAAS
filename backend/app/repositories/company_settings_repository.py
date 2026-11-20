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


DEFAULT_ROLES = ["COMPANY_ADMIN", "COMPANY_MANAGER", "COMPANY_EMPLOYEE", "COMPANY_CLIENT"]


def ensure_tenant_defaults(cursor: Any, company_id: UUID | str) -> bool:
    """Create the company's settings row when it is missing, with the same defaults company
    setup uses (colours, theme, the company's timezone and language, role permissions). Returns
    True when a row was added."""
    cursor.execute(
        "SELECT r.code, m.code, p.code FROM role_permissions rp "
        "JOIN roles r ON r.id = rp.role_id JOIN modules m ON m.id = rp.module_id "
        "JOIN permissions p ON p.id = rp.permission_id "
        "WHERE r.code = ANY(%s) ORDER BY r.code, m.code, p.code",
        (DEFAULT_ROLES,),
    )
    permissions: dict[str, list[str]] = {code: [] for code in DEFAULT_ROLES}
    for role_code, module_code, permission_code in cursor.fetchall():
        permissions[str(role_code)].append(f"{module_code}_{permission_code}")
    cursor.execute(
        "INSERT INTO company_tenant_defaults (company_id, primary_color, secondary_color, "
        "accent_color, theme, timezone, language, default_roles, default_permissions, "
        "notification_preferences, dashboard_configuration, created_at, updated_at) "
        "SELECT c.id, '#0876ED', '#065EC1', '#0876ED', 'system', "
        "COALESCE(NULLIF(c.timezone, ''), 'Asia/Kolkata'), COALESCE(NULLIF(c.language, ''), 'en'), "
        "%s, %s, %s, %s, NOW(), NOW() FROM companies c WHERE c.id = %s "
        "ON CONFLICT (company_id) DO NOTHING",
        (
            Jsonb(DEFAULT_ROLES),
            Jsonb(permissions),
            Jsonb({"email": True, "in_app": True}),
            Jsonb({"layout": "default", "widgets": []}),
            company_id,
        ),
    )
    return bool(cursor.rowcount)


def repair_missing_tenant_defaults() -> int:
    """At startup: every company without a settings row gets one. Never raises."""
    import logging

    try:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT c.id FROM companies c LEFT JOIN company_tenant_defaults d "
                "ON d.company_id = c.id WHERE d.company_id IS NULL"
            )
            missing = [row[0] for row in cursor.fetchall()]
            for company_id in missing:
                ensure_tenant_defaults(cursor, company_id)
            if missing:
                logging.getLogger(__name__).warning(
                    "Added missing company settings for %s companies.", len(missing)
                )
            return len(missing)
    except Exception:  # noqa: BLE001 - startup must go on
        logging.getLogger(__name__).warning("Company settings repair failed", exc_info=True)
        return 0


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
                if row is None and ensure_tenant_defaults(cursor, company_id):
                    # A company made without its settings row gets one (owner report 2026-11-20:
                    # "Company settings are not initialized" on the Settings page).
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
