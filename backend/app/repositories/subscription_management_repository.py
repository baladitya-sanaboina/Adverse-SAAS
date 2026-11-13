from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from app.database.connectivity import database_pool
from app.schemas.subscription_management import PlanListFilters, PlanPayload, PlanUpdateRequest


@dataclass(frozen=True)
class PlanRecord:
    id: UUID
    name: str
    code: str
    description: str | None
    monthly_price: Decimal
    yearly_price: Decimal
    status: str
    display_order: int
    features: dict[str, bool]
    limits: dict[str, int | None]
    companies_using_plan: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class CompanyPlanRecord:
    company_id: UUID
    company_name: str
    plan: PlanRecord
    status: str
    activation_date: datetime
    expiration_date: datetime | None
    previous_display_order: int | None


class SubscriptionManagementRepository:
    _select = """
        SELECT p.id,p.name,p.code,p.description,p.monthly_price,p.yearly_price,p.status::text,
        p.display_order,COALESCE(f.items,'{}'::jsonb),COALESCE(l.items,'{}'::jsonb),
        COUNT(cs.id)::int,p.created_at,p.updated_at
        FROM subscription_plans p
        LEFT JOIN LATERAL (SELECT jsonb_object_agg(feature_code,enabled) items FROM subscription_plan_features WHERE plan_id=p.id) f ON TRUE
        LEFT JOIN LATERAL (SELECT jsonb_object_agg(limit_code,value) items FROM subscription_plan_limits WHERE plan_id=p.id) l ON TRUE
        LEFT JOIN company_subscriptions cs ON cs.plan_id=p.id AND cs.status='ACTIVE'
    """
    _group = " GROUP BY p.id,f.items,l.items "

    @staticmethod
    def _record(row: tuple[Any, ...]) -> PlanRecord:
        return PlanRecord(
            id=row[0],
            name=row[1],
            code=row[2],
            description=row[3],
            monthly_price=row[4],
            yearly_price=row[5],
            status=row[6],
            display_order=row[7],
            features=dict(row[8]),
            limits={
                key: int(value) if value is not None else None
                for key, value in dict(row[9]).items()
            },
            companies_using_plan=row[10],
            created_at=row[11],
            updated_at=row[12],
        )

    def list_plans(self, filters: PlanListFilters) -> tuple[tuple[PlanRecord, ...], int]:
        clauses: list[str] = []
        values: list[Any] = []
        if filters.search:
            clauses.append("(p.name ILIKE %s OR p.code ILIKE %s)")
            values.extend((f"%{filters.search}%", f"%{filters.search}%"))
        if filters.status:
            clauses.append("p.status=%s")
            values.append(filters.status)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        order = {
            "newest": "p.created_at DESC",
            "oldest": "p.created_at ASC",
            "a-z": "p.name ASC",
            "z-a": "p.name DESC",
            "display-order": "p.display_order,p.name",
        }[filters.sort]
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(f"SELECT COUNT(*) FROM subscription_plans p{where}", values)
                count_row = cursor.fetchone()
                total = int(count_row[0]) if count_row else 0
                cursor.execute(
                    f"{self._select}{where}{self._group}ORDER BY {order} LIMIT %s OFFSET %s",
                    (*values, filters.page_size, (filters.page - 1) * filters.page_size),
                )
                return tuple(self._record(row) for row in cursor.fetchall()), total

    def get_plan(self, plan_id: UUID) -> PlanRecord | None:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(f"{self._select} WHERE p.id=%s{self._group}", (plan_id,))
                row = cursor.fetchone()
                return self._record(row) if row else None

    def get_company_plan(self, company_id: UUID) -> PlanRecord | None:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"{self._select} JOIN company_subscriptions current_subscription ON current_subscription.plan_id=p.id AND current_subscription.status='ACTIVE' WHERE current_subscription.company_id=%s{self._group}",
                    (company_id,),
                )
                row = cursor.fetchone()
                return self._record(row) if row else None

    def code_exists(self, code: str, exclude_id: UUID | None = None) -> bool:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT EXISTS(SELECT 1 FROM subscription_plans WHERE code=%s AND (%s::uuid IS NULL OR id<>%s::uuid))",
                    (code, exclude_id, exclude_id),
                )
                exists_row = cursor.fetchone()
                return bool(exists_row[0]) if exists_row else False

    @staticmethod
    def _replace_configuration(
        cursor: Any, plan_id: UUID, payload: PlanPayload | PlanUpdateRequest
    ) -> None:
        cursor.execute("DELETE FROM subscription_plan_features WHERE plan_id=%s", (plan_id,))
        cursor.execute("DELETE FROM subscription_plan_limits WHERE plan_id=%s", (plan_id,))
        if payload.features:
            cursor.executemany(
                "INSERT INTO subscription_plan_features(plan_id,feature_code,enabled) VALUES(%s,%s,%s)",
                [(plan_id, key, value) for key, value in payload.features.items()],
            )
        if payload.limits:
            cursor.executemany(
                "INSERT INTO subscription_plan_limits(plan_id,limit_code,value) VALUES(%s,%s,%s)",
                [(plan_id, key, value) for key, value in payload.limits.items()],
            )

    def create_plan(self, actor_id: UUID, payload: PlanPayload) -> PlanRecord:
        plan_id = uuid4()
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO subscription_plans(id,name,code,description,monthly_price,yearly_price,status,display_order,created_at,updated_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,NOW(),NOW())",
                    (
                        plan_id,
                        payload.name,
                        payload.code,
                        payload.description,
                        payload.monthly_price,
                        payload.yearly_price,
                        payload.status,
                        payload.display_order,
                    ),
                )
                self._replace_configuration(cursor, plan_id, payload)
                cursor.execute(
                    "INSERT INTO subscription_audits(id,actor_id,plan_id,action) VALUES(%s,%s,%s,'PLAN_CREATED')",
                    (uuid4(), actor_id, plan_id),
                )
        return self.get_plan(plan_id)  # type: ignore[return-value]

    def update_plan(
        self, actor_id: UUID, plan_id: UUID, payload: PlanUpdateRequest
    ) -> PlanRecord | None:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT status::text FROM subscription_plans WHERE id=%s FOR UPDATE",
                    (plan_id,),
                )
                current_row = cursor.fetchone()
                if not current_row:
                    return None
                previous_status = str(current_row[0])
                cursor.execute(
                    "UPDATE subscription_plans SET name=%s,description=%s,monthly_price=%s,yearly_price=%s,status=%s,display_order=%s,updated_at=NOW() WHERE id=%s RETURNING id",
                    (
                        payload.name,
                        payload.description,
                        payload.monthly_price,
                        payload.yearly_price,
                        payload.status,
                        payload.display_order,
                        plan_id,
                    ),
                )
                cursor.fetchone()
                self._replace_configuration(cursor, plan_id, payload)
                cursor.execute(
                    "INSERT INTO subscription_audits(id,actor_id,plan_id,action) VALUES(%s,%s,%s,'PLAN_UPDATED')",
                    (uuid4(), actor_id, plan_id),
                )
                if previous_status != payload.status:
                    status_action = (
                        "PLAN_ACTIVATED" if payload.status == "ACTIVE" else "PLAN_DEACTIVATED"
                    )
                    cursor.execute(
                        "INSERT INTO subscription_audits(id,actor_id,plan_id,action) VALUES(%s,%s,%s,%s)",
                        (uuid4(), actor_id, plan_id, status_action),
                    )
        return self.get_plan(plan_id)

    def assign_plan(
        self,
        actor_id: UUID,
        company_id: UUID,
        plan_id: UUID,
        activation_date: datetime,
        expiration_date: datetime | None,
    ) -> CompanyPlanRecord | None:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT c.name,cs.plan_id,p.display_order FROM companies c LEFT JOIN company_subscriptions cs ON cs.company_id=c.id LEFT JOIN subscription_plans p ON p.id=cs.plan_id WHERE c.id=%s FOR UPDATE OF c",
                    (company_id,),
                )
                company = cursor.fetchone()
                if not company:
                    return None
                cursor.execute(
                    "SELECT name,display_order,status::text FROM subscription_plans WHERE id=%s",
                    (plan_id,),
                )
                target = cursor.fetchone()
                if not target:
                    return None
                if target[2] != "ACTIVE":
                    raise ValueError("Inactive plans cannot be assigned.")
                previous_order = company[2]
                change = (
                    "PLAN_ASSIGNED"
                    if company[1] is None
                    else (
                        "PLAN_UPGRADED"
                        if target[1] > previous_order
                        else "PLAN_DOWNGRADED" if target[1] < previous_order else "PLAN_CHANGED"
                    )
                )
                cursor.execute(
                    "INSERT INTO company_subscriptions(id,company_id,plan_id,status,activation_date,expiration_date,created_at,updated_at) VALUES(%s,%s,%s,'ACTIVE',%s,%s,NOW(),NOW()) ON CONFLICT(company_id) DO UPDATE SET plan_id=EXCLUDED.plan_id,status='ACTIVE',activation_date=EXCLUDED.activation_date,expiration_date=EXCLUDED.expiration_date,updated_at=NOW()",
                    (uuid4(), company_id, plan_id, activation_date, expiration_date),
                )
                cursor.execute(
                    "UPDATE companies SET subscription_plan=%s,updated_at=NOW() WHERE id=%s",
                    (target[0], company_id),
                )
                cursor.execute(
                    "INSERT INTO subscription_audits(id,actor_id,company_id,plan_id,action) VALUES(%s,%s,%s,%s,%s)",
                    (uuid4(), actor_id, company_id, plan_id, change),
                )
        plan = self.get_plan(plan_id)
        return (
            CompanyPlanRecord(
                company_id,
                company[0],
                plan,
                "ACTIVE",
                activation_date,
                expiration_date,
                previous_order,
            )
            if plan
            else None
        )

    def is_ready(self) -> bool:
        try:
            with database_pool.connection(timeout=2) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT to_regclass('public.subscription_plans') IS NOT NULL AND to_regclass('public.company_subscriptions') IS NOT NULL"
                    )
                    ready_row = cursor.fetchone()
                    return bool(ready_row[0]) if ready_row else False
        except Exception:
            return False
