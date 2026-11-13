from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from app.database.connectivity import database_pool
from app.schemas.audit_logs import AuditLogFilters


@dataclass(frozen=True)
class AuditLogRecord:
    id: UUID
    category: str
    action: str
    actor_id: UUID | None
    actor_name: str
    actor_email: str
    company_id: UUID | None
    company_name: str | None
    target: str | None
    details: str | None
    created_at: datetime


class AuditLogRepository:
    _events = """
        SELECT id,'DEVELOPER'::text category,action,actor_id,NULL::uuid company_id,
               target_developer_id::text target,details::text,created_at FROM developer_audits
        UNION ALL
        SELECT id,'COMPANY',action,actor_id,company_id,company_id::text,
               CONCAT_WS(' → ',previous_status,new_status),created_at FROM company_management_audits
        UNION ALL
        SELECT id,'SUBSCRIPTION',action,actor_id,company_id,plan_id::text,details::text,created_at
          FROM subscription_audits
        UNION ALL
        SELECT id,'PLATFORM_SETTINGS',action,actor_id,NULL::uuid,'global',
               CONCAT_WS(' · ',changed_fields,previous_value,new_value),created_at
          FROM platform_setting_audits
        UNION ALL
        SELECT id,'ONBOARDING',action,actor_id,company_id,company_id::text,details::text,created_at
          FROM company_onboarding_audits
        UNION ALL
        SELECT id,'COMPANY_SETTINGS',action,actor_id,company_id,company_id::text,details::text,created_at
          FROM company_setting_audits
        UNION ALL
        SELECT id,'REGISTRATION',action::text,actor_id,company_id,created_user_id::text,
               role_code,created_at FROM registration_audits
        UNION ALL
        SELECT id,'ENFORCEMENT',event_type,actor_id,company_id,resource_code,
               CONCAT_WS(' · ',details,'usage=' || current_usage,'limit=' || COALESCE(configured_limit::text,'unlimited')),
               created_at FROM subscription_enforcement_audits
        UNION ALL
        SELECT id,'ORGANIZATION',action,actor_id,company_id,entity_id::text,
               CONCAT_WS(' · ',entity_type,details::text),created_at FROM organization_audits
        UNION ALL
        SELECT id,'INVITATION',action,actor_id,company_id,invitation_id::text,
               details::text,created_at FROM invitation_audits
        UNION ALL
        SELECT id,'PROFILE',action::text,user_id,company_id,user_id::text,
               NULL::text,created_at FROM profile_audits
        UNION ALL
        SELECT id,'AUTHENTICATION',event_type::text,user_id,company_id,
               COALESCE(session_id::text,email),CONCAT_WS(' · ',email,details),created_at
          FROM authentication_events
        UNION ALL
        SELECT id,'EMPLOYEE',action,actor_id,company_id,employee_id::text,
               details::text,created_at FROM employee_audits
        UNION ALL
        SELECT id,'CRM',action,actor_id,company_id,entity_id::text,
               CONCAT_WS(' · ',entity_type,details::text),created_at FROM crm_audits
    """

    def actor_is_platform_owner(self, actor_id: UUID) -> bool:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT EXISTS(SELECT 1 FROM users u JOIN roles r ON r.id=u.role_id "
                    "WHERE u.id=%s AND r.code='PLATFORM_OWNER' AND u.status='ACTIVE')",
                    (actor_id,),
                )
                row = cursor.fetchone()
                return bool(row and row[0])

    @staticmethod
    def _where(filters: AuditLogFilters) -> tuple[str, list[Any]]:
        clauses: list[str] = []
        values: list[Any] = []
        if filters.category:
            clauses.append("e.category=%s")
            values.append(filters.category)
        if filters.date:
            clauses.append("e.created_at >= %s AND e.created_at < (%s::date + INTERVAL '1 day')")
            values.extend((filters.date, filters.date))
        if filters.search:
            clauses.append(
                "(e.action ILIKE %s OR e.category ILIKE %s OR COALESCE(u.name,'') ILIKE %s "
                "OR COALESCE(u.email,'') ILIKE %s OR COALESCE(c.name,'') ILIKE %s "
                "OR COALESCE(e.target,'') ILIKE %s OR COALESCE(e.details,'') ILIKE %s)"
            )
            search = f"%{filters.search}%"
            values.extend([search] * 7)
        return (f" WHERE {' AND '.join(clauses)}" if clauses else "", values)

    def list_logs(self, filters: AuditLogFilters) -> tuple[tuple[AuditLogRecord, ...], int]:
        where, values = self._where(filters)
        order = "DESC" if filters.sort == "newest" else "ASC"
        base = (
            f"WITH events AS ({self._events}) SELECT e.id,e.category,e.action,e.actor_id,"
            "COALESCE(u.name,'Unknown user'),COALESCE(u.email,'unknown'),e.company_id,c.name,"
            "e.target,e.details,e.created_at FROM events e LEFT JOIN users u ON u.id=e.actor_id "
            "LEFT JOIN companies c ON c.id=e.company_id"
        )
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"WITH events AS ({self._events}) SELECT COUNT(*) FROM events e "
                    "LEFT JOIN users u ON u.id=e.actor_id LEFT JOIN companies c ON c.id=e.company_id"
                    f"{where}",
                    values,
                )
                row = cursor.fetchone()
                total = int(row[0]) if row else 0
                cursor.execute(
                    f"{base}{where} ORDER BY e.created_at {order} LIMIT %s OFFSET %s",
                    (*values, filters.page_size, (filters.page - 1) * filters.page_size),
                )
                return tuple(AuditLogRecord(*row) for row in cursor.fetchall()), total

    def summary(self) -> dict[str, int]:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"WITH events AS ({self._events}) SELECT category,COUNT(*)::int "
                    "FROM events GROUP BY category ORDER BY category"
                )
                return {str(row[0]): int(row[1]) for row in cursor.fetchall()}

    def is_ready(self) -> bool:
        try:
            with database_pool.connection(timeout=2) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"WITH events AS ({self._events}) SELECT COUNT(*) >= 0 FROM events"
                    )
                    row = cursor.fetchone()
                    return bool(row and row[0])
        except Exception:
            return False
