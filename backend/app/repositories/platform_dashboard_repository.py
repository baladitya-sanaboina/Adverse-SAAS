from dataclasses import dataclass
from datetime import datetime

from app.database.connectivity import database_pool


@dataclass(frozen=True)
class PlatformStatisticsRecord:
    total_companies: int
    total_developers: int
    total_employees: int
    total_clients: int
    total_active_users: int
    total_suspended_companies: int
    total_active_sessions: int


@dataclass(frozen=True)
class PlatformActivityRecord:
    action: str
    subject: str
    description: str
    occurred_at: datetime


class PlatformDashboardRepository:
    def load_statistics(self) -> PlatformStatisticsRecord:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT "
                    '(SELECT COUNT(*) FROM "companies"), '
                    '(SELECT COUNT(*) FROM "users" u JOIN "roles" r ON r.id=u.role_id WHERE r.code=%s), '
                    '(SELECT COUNT(*) FROM "users" u JOIN "roles" r ON r.id=u.role_id WHERE r.code=%s), '
                    '(SELECT COUNT(*) FROM "users" u JOIN "roles" r ON r.id=u.role_id WHERE r.code=%s), '
                    "(SELECT COUNT(*) FROM \"users\" WHERE status='ACTIVE'), "
                    "(SELECT COUNT(*) FROM \"companies\" WHERE status='SUSPENDED'), "
                    "(SELECT COUNT(*) FROM \"auth_sessions\" WHERE status='ACTIVE' AND expires_at>NOW())",
                    ("DEVELOPER", "COMPANY_EMPLOYEE", "COMPANY_CLIENT"),
                )
                record = cursor.fetchone()
                if record is None:
                    raise RuntimeError("Platform statistics query returned no result.")
                return PlatformStatisticsRecord(*record)

    def load_recent_activities(self, limit: int = 8) -> tuple[PlatformActivityRecord, ...]:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT action, subject, description, occurred_at FROM ("
                    "SELECT ra.action::text AS action, "
                    "COALESCE(c.name, created.name, ra.role_code, 'Platform') AS subject, "
                    "CASE WHEN ra.action='COMPANY_CREATED' THEN 'Company created' "
                    "ELSE COALESCE(ra.role_code, 'User') || ' registered' END AS description, "
                    "ra.created_at AS occurred_at FROM registration_audits ra "
                    "LEFT JOIN companies c ON c.id=ra.company_id "
                    "LEFT JOIN users created ON created.id=ra.created_user_id "
                    "UNION ALL "
                    "SELECT ae.event_type::text, COALESCE(u.name, ae.email, 'Account'), "
                    "CASE ae.event_type::text WHEN 'PASSWORD_RESET' THEN 'Password reset completed' "
                    "WHEN 'EMAIL_VERIFIED' THEN 'Email verified' ELSE REPLACE(INITCAP(ae.event_type::text), '_', ' ') END, "
                    "ae.created_at FROM authentication_events ae "
                    "LEFT JOIN users u ON u.id=ae.user_id "
                    "WHERE ae.event_type::text IN ('PASSWORD_RESET','EMAIL_VERIFIED')"
                    ") activities ORDER BY occurred_at DESC LIMIT %s",
                    (limit,),
                )
                return tuple(PlatformActivityRecord(*record) for record in cursor.fetchall())

    def foundation_is_ready(self) -> bool:
        try:
            self.load_statistics()
            return True
        except Exception:
            return False
