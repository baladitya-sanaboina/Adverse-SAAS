import re
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Literal, cast
from uuid import UUID, uuid4

from psycopg.errors import UniqueViolation
from psycopg.types.json import Jsonb

from app.database.connectivity import database_pool
from app.schemas.service_pricing import CompanyServiceListFilters

ServicePricingScope = Literal["CLIENT", "MANAGER"]

_DEFAULT_SERVICES: tuple[dict[str, object], ...] = (
    {
        "name": "Reel",
        "code": "REEL",
        "description": "Short-form reel production service.",
        "client_pricing_model": "PER_VIDEO",
        "manager_pricing_model": "COMMISSION_PER_DELIVERABLE",
        "sort_order": 10,
    },
    {
        "name": "Thumbnail",
        "code": "THUMBNAIL",
        "description": "Thumbnail design and export service.",
        "client_pricing_model": "PER_PIECE",
        "manager_pricing_model": "COMMISSION_PER_DELIVERABLE",
        "sort_order": 20,
    },
    {
        "name": "Carousel",
        "code": "CAROUSEL",
        "description": "Carousel content design service.",
        "client_pricing_model": "PER_PIECE",
        "manager_pricing_model": "COMMISSION_PER_DELIVERABLE",
        "sort_order": 30,
    },
    {
        "name": "Long Video",
        "code": "LONG_VIDEO",
        "description": "Long-form video editing and delivery service.",
        "client_pricing_model": "PER_VIDEO",
        "manager_pricing_model": "COMMISSION_PER_DELIVERABLE",
        "sort_order": 40,
    },
    {
        "name": "SPLS Reel",
        "code": "SPLS_REEL",
        "description": "Specialized SPLS reel production service.",
        "client_pricing_model": "PER_VIDEO",
        "manager_pricing_model": "COMMISSION_PER_DELIVERABLE",
        "sort_order": 50,
    },
    {
        "name": "Social Media Marketing",
        "code": "SOCIAL_MEDIA_MARKETING",
        "description": "Recurring social media marketing package.",
        "client_pricing_model": "MONTHLY_FIXED",
        "manager_pricing_model": "COMMISSION_PER_DELIVERABLE",
        "sort_order": 60,
    },
)


def seed_default_services(cursor: Any, company_id: UUID) -> None:
    for service in _DEFAULT_SERVICES:
        cursor.execute(
            """
            INSERT INTO company_services(
                id,company_id,name,code,description,client_pricing_model,manager_pricing_model,
                status,sort_order,created_at,updated_at
            ) VALUES(
                %s,%s,%s,%s,%s,%s::"ServicePricingModel",%s::"ServicePricingModel",
                'ACTIVE',%s,NOW(),NOW()
            )
            ON CONFLICT (company_id, code) DO NOTHING
            """,
            (
                uuid4(),
                company_id,
                service["name"],
                service["code"],
                service["description"],
                service["client_pricing_model"],
                service["manager_pricing_model"],
                service["sort_order"],
            ),
        )


@dataclass(frozen=True)
class CompanyServiceRecord:
    id: UUID
    company_id: UUID
    name: str
    code: str
    description: str
    client_pricing_model: str
    manager_pricing_model: str
    status: str
    sort_order: int
    created_at: datetime
    updated_at: datetime
    active_client_rates: int
    active_manager_rates: int
    pricing_history_entries: int
    safe_to_delete: bool


@dataclass(frozen=True)
class PricingSubjectRecord:
    id: UUID
    name: str
    subtitle: str


@dataclass(frozen=True)
class ServicePricingRecord:
    id: UUID
    scope: str
    pricing_model: str
    amount: Decimal
    currency: str
    notes: str
    effective_from: datetime
    effective_to: datetime | None
    created_by_id: UUID
    created_by_name: str
    created_at: datetime
    service_id: UUID | None = None
    service_name: str | None = None
    service_code: str | None = None
    service_description: str | None = None
    service_status: str | None = None


@dataclass(frozen=True)
class PricingOverviewItemRecord:
    service_id: UUID
    service_name: str
    service_code: str
    service_description: str
    service_status: str
    default_pricing_model: str
    current_rate_id: UUID | None
    current_rate_scope: str | None
    current_pricing_model: str | None
    current_amount: Decimal | None
    current_currency: str | None
    current_notes: str | None
    current_effective_from: datetime | None
    current_effective_to: datetime | None
    current_created_by_id: UUID | None
    current_created_by_name: str | None
    current_created_at: datetime | None
    history_count: int


class ServiceCatalogConflict(Exception):
    def __init__(self, field: str):
        self.field = field


class ServiceCatalogReferenceError(Exception):
    def __init__(self, reference: str):
        self.reference = reference


class ServiceDeleteBlocked(Exception):
    pass


class ServicePricingConflict(Exception):
    def __init__(self, reason: str):
        self.reason = reason


class ServicePricingRepository:
    _service_fields = (
        "s.id,s.company_id,s.name,s.code,s.description,s.client_pricing_model::text,"
        "s.manager_pricing_model::text,s.status::text,s.sort_order,s.created_at,s.updated_at,"
        "COALESCE(client_rates.count,0),COALESCE(manager_rates.count,0),COALESCE(history.count,0),"
        "COALESCE(history.count,0)=0"
    )
    _service_joins = (
        " FROM company_services s "
        "LEFT JOIN LATERAL ("
        "  SELECT COUNT(*)::int AS count FROM service_pricing sp "
        "  WHERE sp.service_id=s.id AND sp.scope='CLIENT' AND sp.effective_to IS NULL"
        ") client_rates ON TRUE "
        "LEFT JOIN LATERAL ("
        "  SELECT COUNT(*)::int AS count FROM service_pricing sp "
        "  WHERE sp.service_id=s.id AND sp.scope='MANAGER' AND sp.effective_to IS NULL"
        ") manager_rates ON TRUE "
        "LEFT JOIN LATERAL ("
        "  SELECT COUNT(*)::int AS count FROM service_pricing sp WHERE sp.service_id=s.id"
        ") history ON TRUE "
    )

    @staticmethod
    def service_code(name: str) -> str:
        normalized = re.sub(r"[^A-Za-z0-9]+", "_", name.strip().upper()).strip("_")
        return normalized or "SERVICE"

    @staticmethod
    def _service_record(row: tuple[Any, ...]) -> CompanyServiceRecord:
        return CompanyServiceRecord(*row)

    @staticmethod
    def _pricing_record(row: tuple[Any, ...]) -> ServicePricingRecord:
        return ServicePricingRecord(*row)

    @staticmethod
    def _overview_item(row: tuple[Any, ...]) -> PricingOverviewItemRecord:
        return PricingOverviewItemRecord(*row)

    @staticmethod
    def _subject_column(scope: ServicePricingScope) -> str:
        return "client_id" if scope == "CLIENT" else "manager_user_id"

    @staticmethod
    def _default_model_column(scope: ServicePricingScope) -> str:
        return "client_pricing_model" if scope == "CLIENT" else "manager_pricing_model"

    def list_services(
        self, company_id: UUID, filters: CompanyServiceListFilters
    ) -> tuple[tuple[CompanyServiceRecord, ...], int]:
        clauses = ["s.company_id=%s"]
        values: list[object] = [company_id]
        if filters.search:
            clauses.append("(s.name ILIKE %s OR s.code ILIKE %s OR s.description ILIKE %s)")
            pattern = f"%{filters.search}%"
            values.extend((pattern, pattern, pattern))
        if filters.status is not None:
            clauses.append("s.status=%s")
            values.append(filters.status)
        where = " AND ".join(clauses)
        with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
            cursor.execute(f"SELECT COUNT(*){self._service_joins}WHERE {where}", values)
            total_row = cursor.fetchone()
            total = int(total_row[0]) if total_row else 0
            cursor.execute(
                f"SELECT {self._service_fields}{self._service_joins}WHERE {where} "
                "ORDER BY CASE WHEN s.status='ACTIVE' THEN 0 ELSE 1 END, s.sort_order ASC, s.name ASC "
                "LIMIT %s OFFSET %s",
                (*values, filters.page_size, (filters.page - 1) * filters.page_size),
            )
            return tuple(self._service_record(row) for row in cursor.fetchall()), total

    def get_service(self, company_id: UUID, service_id: UUID) -> CompanyServiceRecord | None:
        with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
            cursor.execute(
                f"SELECT {self._service_fields}{self._service_joins}WHERE s.company_id=%s AND s.id=%s",
                (company_id, service_id),
            )
            row = cursor.fetchone()
            return self._service_record(row) if row else None

    def create_service(
        self, company_id: UUID, actor_id: UUID, values: dict[str, object]
    ) -> CompanyServiceRecord:
        columns = ["id", "company_id", *values.keys(), "created_at", "updated_at"]
        params = [uuid4(), company_id, *values.values()]
        placeholders = ["%s"] * (2 + len(values)) + ["NOW()", "NOW()"]
        try:
            with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
                cursor.execute(
                    f"INSERT INTO company_services({','.join(columns)}) VALUES({','.join(placeholders)}) RETURNING id",
                    params,
                )
                created = cursor.fetchone()
                if created is None:
                    raise RuntimeError("The service insert returned no id.")
                service_id = created[0]
                self._audit(
                    cursor,
                    actor_id,
                    company_id,
                    "SERVICE_CREATED",
                    {
                        "service_id": str(service_id),
                        "service_name": values.get("name"),
                        "service_code": values.get("code"),
                    },
                )
            record = self.get_service(company_id, service_id)
            if record is None:
                raise RuntimeError("Service insert returned no record.")
            return record
        except UniqueViolation as error:
            constraint = error.diag.constraint_name or ""
            if constraint.endswith("_name_key"):
                raise ServiceCatalogConflict("name") from error
            raise ServiceCatalogConflict("code") from error

    def update_service(
        self,
        company_id: UUID,
        actor_id: UUID,
        service_id: UUID,
        values: dict[str, object],
    ) -> CompanyServiceRecord | None:
        setters = ",".join(f"{column}=%s" for column in values)
        try:
            with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
                cursor.execute(
                    f"UPDATE company_services SET {setters},updated_at=NOW() WHERE id=%s AND company_id=%s",
                    (*values.values(), service_id, company_id),
                )
                if cursor.rowcount == 0:
                    return None
                self._audit(
                    cursor,
                    actor_id,
                    company_id,
                    "SERVICE_UPDATED",
                    {"service_id": str(service_id), "changed_fields": sorted(values)},
                )
            return self.get_service(company_id, service_id)
        except UniqueViolation as error:
            constraint = error.diag.constraint_name or ""
            if constraint.endswith("_name_key"):
                raise ServiceCatalogConflict("name") from error
            raise ServiceCatalogConflict("code") from error

    def delete_service(self, company_id: UUID, actor_id: UUID, service_id: UUID) -> bool:
        with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM company_services WHERE id=%s AND company_id=%s FOR UPDATE",
                (service_id, company_id),
            )
            if cursor.fetchone() is None:
                return False
            cursor.execute(
                "SELECT COUNT(*) FROM service_pricing WHERE company_id=%s AND service_id=%s",
                (company_id, service_id),
            )
            row = cursor.fetchone()
            if row and int(row[0]) > 0:
                raise ServiceDeleteBlocked
            cursor.execute(
                "DELETE FROM company_services WHERE id=%s AND company_id=%s",
                (service_id, company_id),
            )
            self._audit(
                cursor,
                actor_id,
                company_id,
                "SERVICE_DELETED",
                {"service_id": str(service_id)},
            )
            return True

    def get_subject(
        self, company_id: UUID, scope: ServicePricingScope, subject_id: UUID
    ) -> PricingSubjectRecord | None:
        with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
            return self._get_subject(cursor, company_id, scope, subject_id)

    def list_pricing_overview(
        self, company_id: UUID, scope: ServicePricingScope, subject_id: UUID
    ) -> tuple[PricingOverviewItemRecord, ...]:
        subject_column = self._subject_column(scope)
        default_column = self._default_model_column(scope)
        with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT
                    s.id,
                    s.name,
                    s.code,
                    s.description,
                    s.status::text,
                    s.{default_column}::text,
                    current_rate.id,
                    current_rate.scope::text,
                    current_rate.pricing_model::text,
                    current_rate.amount,
                    current_rate.currency,
                    current_rate.notes,
                    current_rate.effective_from,
                    current_rate.effective_to,
                    current_rate.created_by_id,
                    creator.name,
                    current_rate.created_at,
                    COALESCE(history.count,0)
                FROM company_services s
                LEFT JOIN LATERAL (
                    SELECT sp.id,sp.scope,sp.pricing_model,sp.amount,sp.currency,sp.notes,
                        sp.effective_from,sp.effective_to,sp.created_by_id,sp.created_at
                    FROM service_pricing sp
                    WHERE sp.company_id=%s AND sp.service_id=s.id AND sp.scope=%s AND sp.{subject_column}=%s
                      AND sp.effective_from <= NOW()
                      AND (sp.effective_to IS NULL OR sp.effective_to > NOW())
                    ORDER BY sp.effective_from DESC, sp.created_at DESC
                    LIMIT 1
                ) current_rate ON TRUE
                LEFT JOIN users creator ON creator.id=current_rate.created_by_id
                LEFT JOIN LATERAL (
                    SELECT COUNT(*)::int AS count
                    FROM service_pricing sp
                    WHERE sp.company_id=%s AND sp.service_id=s.id AND sp.scope=%s AND sp.{subject_column}=%s
                ) history ON TRUE
                WHERE s.company_id=%s
                ORDER BY CASE WHEN s.status='ACTIVE' THEN 0 ELSE 1 END, s.sort_order ASC, s.name ASC
                """,
                (company_id, scope, subject_id, company_id, scope, subject_id, company_id),
            )
            return tuple(self._overview_item(row) for row in cursor.fetchall())

    def list_pricing_history(
        self, company_id: UUID, scope: ServicePricingScope, subject_id: UUID
    ) -> tuple[ServicePricingRecord, ...]:
        subject_column = self._subject_column(scope)
        with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT
                    sp.id,
                    sp.scope::text,
                    sp.pricing_model::text,
                    sp.amount,
                    sp.currency,
                    sp.notes,
                    sp.effective_from,
                    sp.effective_to,
                    sp.created_by_id,
                    creator.name,
                    sp.created_at,
                    s.id,
                    s.name,
                    s.code,
                    s.description,
                    s.status::text
                FROM service_pricing sp
                JOIN company_services s ON s.id=sp.service_id
                JOIN users creator ON creator.id=sp.created_by_id
                WHERE sp.company_id=%s AND sp.scope=%s AND sp.{subject_column}=%s
                ORDER BY s.sort_order ASC, s.name ASC, sp.effective_from DESC, sp.created_at DESC
                """,
                (company_id, scope, subject_id),
            )
            return tuple(self._pricing_record(row) for row in cursor.fetchall())

    def set_pricing(
        self,
        company_id: UUID,
        actor_id: UUID,
        scope: ServicePricingScope,
        subject_id: UUID,
        service_id: UUID,
        values: dict[str, object],
    ) -> ServicePricingRecord:
        subject_column = self._subject_column(scope)
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            service_row = self._get_service_for_update(cursor, company_id, service_id)
            if service_row is None:
                raise ServiceCatalogReferenceError("service")
            if service_row[0] != "ACTIVE":
                raise ServicePricingConflict("service_inactive")
            self._require_subject(cursor, company_id, scope, subject_id)
            currency = self._company_currency(cursor, company_id)
            effective_from = cast(
                datetime, values.get("effective_from") or datetime.now(timezone.utc)
            )
            pricing_model = values.get("pricing_model") or (
                service_row[1] if scope == "CLIENT" else service_row[2]
            )
            notes = str(values.get("notes") or "")
            amount = values["amount"]
            previous = self._previous_pricing(
                cursor, company_id, scope, subject_column, subject_id, service_id, effective_from
            )
            next_row = self._next_pricing(
                cursor, company_id, scope, subject_column, subject_id, service_id, effective_from
            )
            if previous and previous[1] == effective_from:
                if (
                    previous[2] == pricing_model
                    and previous[3] == amount
                    and previous[4] == currency
                    and previous[5] == notes
                ):
                    return self._pricing_by_id(cursor, previous[0])
                raise ServicePricingConflict("effective_from")
            if previous and previous[6] is not None and previous[6] <= effective_from:
                pass
            if previous and (previous[6] is None or previous[6] > effective_from):
                cursor.execute(
                    "UPDATE service_pricing SET effective_to=%s WHERE id=%s",
                    (effective_from, previous[0]),
                )
            effective_to = next_row[1] if next_row else None
            pricing_id = uuid4()
            cursor.execute(
                f"""
                INSERT INTO service_pricing(
                    id,company_id,service_id,scope,{subject_column},pricing_model,amount,currency,
                    notes,effective_from,effective_to,created_by_id,created_at
                ) VALUES(
                    %s,%s,%s,%s,%s,%s::"ServicePricingModel",%s,%s,%s,%s,%s,%s,NOW()
                )
                """,
                (
                    pricing_id,
                    company_id,
                    service_id,
                    scope,
                    subject_id,
                    pricing_model,
                    amount,
                    currency,
                    notes,
                    effective_from,
                    effective_to,
                    actor_id,
                ),
            )
            self._audit(
                cursor,
                actor_id,
                company_id,
                f"{scope}_SERVICE_PRICING_SET",
                {
                    "service_id": str(service_id),
                    f"{subject_column}": str(subject_id),
                    "pricing_model": pricing_model,
                    "amount": str(amount),
                    "currency": currency,
                    "effective_from": effective_from.isoformat(),
                    "effective_to": effective_to.isoformat() if effective_to else None,
                },
            )
            return self._pricing_by_id(cursor, pricing_id)

    def _get_subject(
        self,
        cursor: Any,
        company_id: UUID,
        scope: ServicePricingScope,
        subject_id: UUID,
    ) -> PricingSubjectRecord | None:
        if scope == "CLIENT":
            cursor.execute(
                "SELECT id,name,code FROM clients WHERE id=%s AND company_id=%s",
                (subject_id, company_id),
            )
            row = cursor.fetchone()
            return PricingSubjectRecord(id=row[0], name=row[1], subtitle=row[2]) if row else None
        cursor.execute(
            """
            SELECT u.id,u.name,COALESCE(e.employee_code,u.email)
            FROM users u
            JOIN roles r ON r.id=u.role_id
            LEFT JOIN employees e ON e.user_id=u.id AND e.company_id=u.company_id
            WHERE u.id=%s AND u.company_id=%s AND r.code='COMPANY_MANAGER' AND u.status IN ('ACTIVE','PENDING_VERIFICATION')
            """,
            (subject_id, company_id),
        )
        row = cursor.fetchone()
        return PricingSubjectRecord(id=row[0], name=row[1], subtitle=row[2]) if row else None

    def _require_subject(
        self,
        cursor: Any,
        company_id: UUID,
        scope: ServicePricingScope,
        subject_id: UUID,
    ) -> None:
        if self._get_subject(cursor, company_id, scope, subject_id) is None:
            raise ServiceCatalogReferenceError("client" if scope == "CLIENT" else "manager")

    @staticmethod
    def _company_currency(cursor: Any, company_id: UUID) -> str:
        cursor.execute(
            "SELECT COALESCE(NULLIF(currency,''),'INR') FROM company_tenant_defaults WHERE company_id=%s",
            (company_id,),
        )
        row = cursor.fetchone()
        return str(row[0]).upper() if row and row[0] else "INR"

    @staticmethod
    def _get_service_for_update(
        cursor: Any, company_id: UUID, service_id: UUID
    ) -> tuple[str, str, str] | None:
        cursor.execute(
            "SELECT status::text, client_pricing_model::text, manager_pricing_model::text "
            "FROM company_services WHERE id=%s AND company_id=%s FOR UPDATE",
            (service_id, company_id),
        )
        row = cursor.fetchone()
        return (str(row[0]), str(row[1]), str(row[2])) if row else None

    @staticmethod
    def _previous_pricing(
        cursor: Any,
        company_id: UUID,
        scope: ServicePricingScope,
        subject_column: str,
        subject_id: UUID,
        service_id: UUID,
        effective_from: datetime,
    ) -> tuple[UUID, datetime, str, Decimal, str, str, datetime | None] | None:
        cursor.execute(
            f"""
            SELECT id,effective_from,pricing_model::text,amount,currency,notes,effective_to
            FROM service_pricing
            WHERE company_id=%s AND scope=%s AND {subject_column}=%s AND service_id=%s
              AND effective_from <= %s
            ORDER BY effective_from DESC, created_at DESC
            LIMIT 1
            FOR UPDATE
            """,
            (company_id, scope, subject_id, service_id, effective_from),
        )
        row = cursor.fetchone()
        return tuple(row) if row else None

    @staticmethod
    def _next_pricing(
        cursor: Any,
        company_id: UUID,
        scope: ServicePricingScope,
        subject_column: str,
        subject_id: UUID,
        service_id: UUID,
        effective_from: datetime,
    ) -> tuple[UUID, datetime] | None:
        cursor.execute(
            f"""
            SELECT id,effective_from
            FROM service_pricing
            WHERE company_id=%s AND scope=%s AND {subject_column}=%s AND service_id=%s
              AND effective_from > %s
            ORDER BY effective_from ASC, created_at ASC
            LIMIT 1
            FOR UPDATE
            """,
            (company_id, scope, subject_id, service_id, effective_from),
        )
        row = cursor.fetchone()
        return (row[0], row[1]) if row else None

    def _pricing_by_id(self, cursor: Any, pricing_id: UUID) -> ServicePricingRecord:
        cursor.execute(
            """
            SELECT sp.id,sp.scope::text,sp.pricing_model::text,sp.amount,sp.currency,sp.notes,
                sp.effective_from,sp.effective_to,sp.created_by_id,u.name,sp.created_at
            FROM service_pricing sp
            JOIN users u ON u.id=sp.created_by_id
            WHERE sp.id=%s
            """,
            (pricing_id,),
        )
        row = cursor.fetchone()
        if row is None:
            raise RuntimeError("Pricing write returned no record.")
        return self._pricing_record(row)

    @staticmethod
    def _audit(
        cursor: Any,
        actor_id: UUID,
        company_id: UUID,
        action: str,
        details: dict[str, object] | None,
    ) -> None:
        cursor.execute(
            "INSERT INTO company_setting_audits(id,actor_id,company_id,action,details,created_at) VALUES(%s,%s,%s,%s,%s,NOW())",
            (uuid4(), actor_id, company_id, action, Jsonb(details) if details else None),
        )

    def is_ready(self) -> bool:
        try:
            with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
                cursor.execute(
                    "SELECT to_regclass('public.company_services') IS NOT NULL AND to_regclass('public.service_pricing') IS NOT NULL"
                )
                row = cursor.fetchone()
                return bool(row and row[0])
        except Exception:
            return False
