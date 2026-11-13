from dataclasses import dataclass
from uuid import UUID, uuid4

from app.database.connectivity import database_pool


@dataclass(frozen=True)
class EnforcementSnapshot:
    company_id: UUID
    company_name: str
    plan_id: UUID
    plan_name: str
    plan_code: str
    features: dict[str, bool]
    limits: dict[str, int | None]
    employees_used: int
    clients_used: int
    projects_used: int
    storage_used_bytes: int


class SubscriptionEnforcementRepository:
    def snapshot(self, company_id: UUID) -> EnforcementSnapshot | None:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT c.id,c.name,p.id,p.name,p.code,"
                    "COALESCE((SELECT jsonb_object_agg(feature_code,enabled) FROM subscription_plan_features WHERE plan_id=p.id),'{}'::jsonb),"
                    "COALESCE((SELECT jsonb_object_agg(limit_code,value) FROM subscription_plan_limits WHERE plan_id=p.id),'{}'::jsonb),"
                    "COUNT(u.id) FILTER(WHERE r.code IN ('COMPANY_MANAGER','COMPANY_EMPLOYEE'))::int,"
                    "COUNT(u.id) FILTER(WHERE r.code='COMPANY_CLIENT')::int,"
                    "COALESCE(m.projects_used,0)::bigint,COALESCE(m.storage_used_bytes,0)::bigint "
                    "FROM companies c JOIN company_subscriptions cs ON cs.company_id=c.id AND cs.status='ACTIVE' "
                    "JOIN subscription_plans p ON p.id=cs.plan_id AND p.status='ACTIVE' "
                    "LEFT JOIN users u ON u.company_id=c.id LEFT JOIN roles r ON r.id=u.role_id "
                    "LEFT JOIN company_usage_metrics m ON m.company_id=c.id WHERE c.id=%s "
                    "GROUP BY c.id,p.id,m.projects_used,m.storage_used_bytes",
                    (company_id,),
                )
                row = cursor.fetchone()
                if not row:
                    return None
                return EnforcementSnapshot(
                    company_id=row[0],
                    company_name=row[1],
                    plan_id=row[2],
                    plan_name=row[3],
                    plan_code=row[4],
                    features=dict(row[5]),
                    limits={
                        key: int(value) if value is not None else None
                        for key, value in dict(row[6]).items()
                    },
                    employees_used=int(row[7]),
                    clients_used=int(row[8]),
                    projects_used=int(row[9]),
                    storage_used_bytes=int(row[10]),
                )

    def company_exists(self, company_id: UUID) -> bool:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT EXISTS(SELECT 1 FROM companies WHERE id=%s)", (company_id,))
                row = cursor.fetchone()
                return bool(row and row[0])

    def record_event(
        self,
        company_id: UUID,
        actor_id: UUID | None,
        plan_id: UUID | None,
        event_type: str,
        resource_code: str | None,
        current_usage: int | None = None,
        configured_limit: int | None = None,
        details: str | None = None,
    ) -> None:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO subscription_enforcement_audits(id,company_id,actor_id,plan_id,event_type,resource_code,current_usage,configured_limit,details) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        uuid4(),
                        company_id,
                        actor_id,
                        plan_id,
                        event_type,
                        resource_code,
                        current_usage,
                        configured_limit,
                        details,
                    ),
                )

    def sync_alert(self, company_id: UUID, resource_code: str, level: str, message: str) -> None:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                if level in {"OK", "UNLIMITED"}:
                    cursor.execute(
                        "UPDATE subscription_usage_alerts SET active=FALSE,updated_at=NOW() WHERE company_id=%s AND resource_code=%s",
                        (company_id, resource_code),
                    )
                else:
                    cursor.execute(
                        "INSERT INTO subscription_usage_alerts(id,company_id,resource_code,level,message,active) VALUES(%s,%s,%s,%s,%s,TRUE) ON CONFLICT(company_id,resource_code) DO UPDATE SET level=EXCLUDED.level,message=EXCLUDED.message,active=TRUE,updated_at=NOW()",
                        (uuid4(), company_id, resource_code, level, message),
                    )

    def is_ready(self) -> bool:
        try:
            with database_pool.connection(timeout=2) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT to_regclass('public.company_usage_metrics') IS NOT NULL AND to_regclass('public.subscription_enforcement_audits') IS NOT NULL AND to_regclass('public.subscription_usage_alerts') IS NOT NULL"
                    )
                    row = cursor.fetchone()
                    return bool(row and row[0])
        except Exception:
            return False
