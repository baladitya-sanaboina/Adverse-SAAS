from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from app.database.connectivity import database_pool
from app.schemas.company_management import CompanyListFilters


@dataclass(frozen=True)
class CompanyRecord:
    id: UUID
    name: str
    code: str
    contact_email: str | None
    subscription_plan: str
    status: str
    created_at: datetime
    updated_at: datetime
    admin_id: UUID | None
    admin_name: str | None
    admin_email: str | None
    admin_status: str | None
    total_users: int
    active_users: int
    inactive_users: int


@dataclass(frozen=True)
class CompanyAuditRecord:
    action: str
    actor_name: str
    previous_status: str | None
    new_status: str | None
    created_at: datetime


class CompanyManagementRepository:
    _select = (
        "SELECT c.id,c.name,c.code,c.contact_email,c.subscription_plan,c.status::text,c.created_at,c.updated_at,"
        "a.id,a.name,a.email,a.status::text,"
        "COUNT(u.id)::int,COUNT(u.id) FILTER (WHERE u.status='ACTIVE')::int,"
        "COUNT(u.id) FILTER (WHERE u.status<>'ACTIVE')::int FROM companies c "
        "LEFT JOIN LATERAL (SELECT u.id,u.name,u.email,u.status FROM users u JOIN roles r ON r.id=u.role_id "
        "WHERE u.company_id=c.id AND r.code='COMPANY_ADMIN' ORDER BY u.created_at LIMIT 1) a ON TRUE "
        "LEFT JOIN users u ON u.company_id=c.id "
    )
    _group = " GROUP BY c.id,a.id,a.name,a.email,a.status "

    def list_companies(self, filters: CompanyListFilters) -> tuple[tuple[CompanyRecord, ...], int]:
        clauses: list[str] = []
        values: list[Any] = []
        if filters.search:
            clauses.append("(c.name ILIKE %s OR c.code ILIKE %s OR a.email ILIKE %s)")
            search = f"%{filters.search}%"
            values.extend((search, search, search))
        if filters.status:
            clauses.append("c.status=%s")
            values.append(filters.status)
        if filters.plan:
            clauses.append("c.subscription_plan=%s")
            values.append(filters.plan)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        order = {
            "newest": "c.created_at DESC",
            "oldest": "c.created_at ASC",
            "a-z": "c.name ASC",
            "z-a": "c.name DESC",
        }[filters.sort]
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"SELECT COUNT(DISTINCT c.id) FROM companies c LEFT JOIN LATERAL (SELECT u.email FROM users u JOIN roles r ON r.id=u.role_id WHERE u.company_id=c.id AND r.code='COMPANY_ADMIN' ORDER BY u.created_at LIMIT 1) a ON TRUE{where}",
                    values,
                )
                total_row = cursor.fetchone()
                total = int(total_row[0]) if total_row else 0
                cursor.execute(
                    f"{self._select}{where}{self._group}ORDER BY {order} LIMIT %s OFFSET %s",
                    (*values, filters.page_size, (filters.page - 1) * filters.page_size),
                )
                return tuple(CompanyRecord(*row) for row in cursor.fetchall()), total

    def get_company(self, company_id: UUID) -> CompanyRecord | None:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(f"{self._select} WHERE c.id=%s{self._group}", (company_id,))
                row = cursor.fetchone()
                return CompanyRecord(*row) if row else None

    def summary(self) -> tuple[int, int, int, int, int]:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT COUNT(*)::int,COUNT(*) FILTER(WHERE status='ACTIVE')::int,COUNT(*) FILTER(WHERE status='INACTIVE')::int,COUNT(*) FILTER(WHERE status='SUSPENDED')::int,COUNT(*) FILTER(WHERE status='PENDING')::int FROM companies"
                )
                row = cursor.fetchone()
                if not row:
                    return (0, 0, 0, 0, 0)
                return (int(row[0]), int(row[1]), int(row[2]), int(row[3]), int(row[4]))

    def audits_for(self, company_id: UUID) -> tuple[CompanyAuditRecord, ...]:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT a.action,u.name,a.previous_status,a.new_status,a.created_at FROM company_management_audits a JOIN users u ON u.id=a.actor_id WHERE a.company_id=%s ORDER BY a.created_at DESC LIMIT 20",
                    (company_id,),
                )
                return tuple(CompanyAuditRecord(*row) for row in cursor.fetchall())

    def subscription_for(self, company_id: UUID) -> dict[str, Any]:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT p.id,p.code,cs.status::text,cs.activation_date,cs.expiration_date,"
                    "COALESCE((SELECT jsonb_object_agg(feature_code,enabled) FROM subscription_plan_features WHERE plan_id=p.id),'{}'::jsonb),"
                    "COALESCE((SELECT jsonb_object_agg(limit_code,value) FROM subscription_plan_limits WHERE plan_id=p.id),'{}'::jsonb) "
                    "FROM company_subscriptions cs JOIN subscription_plans p ON p.id=cs.plan_id WHERE cs.company_id=%s",
                    (company_id,),
                )
                row = cursor.fetchone()
                if not row:
                    return {"status": "UNASSIGNED"}
                return {
                    "plan_id": row[0],
                    "plan_code": row[1],
                    "status": row[2],
                    "activation_date": row[3],
                    "expiration_date": row[4],
                    "features": dict(row[5]),
                    "limits": {
                        key: int(value) if value is not None else None
                        for key, value in dict(row[6]).items()
                    },
                }

    def record_view(self, actor_id: UUID, company_id: UUID) -> None:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO company_management_audits(id,actor_id,company_id,action) VALUES(%s,%s,%s,'COMPANY_VIEWED')",
                    (uuid4(), actor_id, company_id),
                )

    def update_status(self, actor_id: UUID, company_id: UUID, status: str) -> CompanyRecord | None:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT status::text FROM companies WHERE id=%s FOR UPDATE", (company_id,)
                )
                row = cursor.fetchone()
                if not row:
                    return None
                previous = row[0]
                cursor.execute(
                    "UPDATE companies SET status=%s,updated_at=NOW() WHERE id=%s",
                    (status, company_id),
                )
                if status != "ACTIVE":
                    cursor.execute(
                        "UPDATE auth_sessions SET status='REVOKED',refresh_token_hash=CONCAT('revoked:',id),last_activity_at=NOW() WHERE company_id=%s AND status='ACTIVE'",
                        (company_id,),
                    )
                action = {"ACTIVE": "COMPANY_ACTIVATED", "SUSPENDED": "COMPANY_SUSPENDED"}.get(
                    status, "COMPANY_STATUS_UPDATED"
                )
                cursor.execute(
                    "INSERT INTO company_management_audits(id,actor_id,company_id,action,previous_status,new_status) VALUES(%s,%s,%s,%s,%s,%s)",
                    (uuid4(), actor_id, company_id, action, previous, status),
                )
        return self.get_company(company_id)

    def is_ready(self) -> bool:
        try:
            with database_pool.connection(timeout=2) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT to_regclass('public.company_management_audits') IS NOT NULL"
                    )
                    row = cursor.fetchone()
                    return bool(row and row[0])
        except Exception:
            return False
