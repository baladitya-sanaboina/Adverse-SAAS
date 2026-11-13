from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.database.connectivity import database_pool


@dataclass(frozen=True)
class CompanyDashboardRecord:
    company_id: UUID
    company_name: str
    logo_url: str | None
    user_id: UUID
    user_name: str
    employees: int
    projects: int
    clients: int


@dataclass(frozen=True)
class CompanyDashboardActivityRecord:
    action: str
    subject: str
    description: str
    occurred_at: datetime


class CompanyDashboardRepository:
    def load(self, company_id: UUID, user_id: UUID) -> CompanyDashboardRecord | None:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT c.id,c.name,d.logo_url,u.id,u.name,"
                    "COUNT(*) FILTER (WHERE member_role.code IN ('COMPANY_MANAGER','COMPANY_EMPLOYEE'))::int,"
                    "COALESCE(MAX(usage.projects_used),0)::bigint,"
                    "COUNT(*) FILTER (WHERE member_role.code='COMPANY_CLIENT') "
                    "FROM companies c JOIN users u ON u.id=%s AND u.company_id=c.id "
                    "LEFT JOIN company_tenant_defaults d ON d.company_id=c.id "
                    "LEFT JOIN company_usage_metrics usage ON usage.company_id=c.id "
                    "LEFT JOIN users member ON member.company_id=c.id "
                    "LEFT JOIN roles member_role ON member_role.id=member.role_id "
                    "WHERE c.id=%s GROUP BY c.id,c.name,d.logo_url,u.id,u.name",
                    (user_id, company_id),
                )
                record = cursor.fetchone()
                return CompanyDashboardRecord(*record) if record else None

    def load_recent_activity(
        self, company_id: UUID, limit: int = 8
    ) -> tuple[CompanyDashboardActivityRecord, ...]:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT action,subject,description,occurred_at FROM ("
                    "SELECT ra.action::text action,COALESCE(created.name,actor.name,'Company member') subject,"
                    "CASE WHEN ra.role_code='COMPANY_MANAGER' THEN 'Manager added to the company' "
                    "WHEN ra.role_code='COMPANY_EMPLOYEE' THEN 'Employee added to the company' "
                    "WHEN ra.role_code='COMPANY_CLIENT' THEN 'Client added to the company' "
                    "ELSE REPLACE(INITCAP(ra.action::text),'_',' ') END description,ra.created_at occurred_at "
                    "FROM registration_audits ra "
                    "LEFT JOIN users created ON created.id=ra.created_user_id "
                    "LEFT JOIN users actor ON actor.id=ra.actor_id WHERE ra.company_id=%s "
                    "UNION ALL "
                    "SELECT csa.action,COALESCE(actor.name,'Company Admin'),"
                    "REPLACE(INITCAP(csa.action),'_',' '),csa.created_at "
                    "FROM company_setting_audits csa LEFT JOIN users actor ON actor.id=csa.actor_id "
                    "WHERE csa.company_id=%s"
                    ") activity ORDER BY occurred_at DESC LIMIT %s",
                    (company_id, company_id, limit),
                )
                return tuple(
                    CompanyDashboardActivityRecord(*record) for record in cursor.fetchall()
                )

    def is_ready(self) -> bool:
        try:
            with database_pool.connection(timeout=2) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT to_regclass('public.companies') IS NOT NULL AND "
                        "to_regclass('public.users') IS NOT NULL AND "
                        "to_regclass('public.company_usage_metrics') IS NOT NULL AND "
                        "to_regclass('public.registration_audits') IS NOT NULL"
                    )
                    record = cursor.fetchone()
                    return bool(record and record[0])
        except Exception:
            return False
