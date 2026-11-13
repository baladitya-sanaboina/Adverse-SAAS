import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from psycopg.errors import UniqueViolation

from app.database.connectivity import database_pool
from app.schemas.crm import LeadListFilters, OpportunityListFilters


@dataclass(frozen=True)
class LeadRecord:
    id: UUID
    company_id: UUID
    client_id: UUID | None
    owner_id: UUID
    owner_name: str
    name: str
    company_name: str
    email: str | None
    phone: str | None
    source: str
    status: str
    notes: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class OpportunityRecord:
    id: UUID
    company_id: UUID
    client_id: UUID
    client_name: str
    lead_id: UUID | None
    owner_id: UUID
    owner_name: str
    name: str
    description: str
    value: Decimal
    currency: str
    stage: str
    status: str
    expected_close_date: date | None
    created_at: datetime
    updated_at: datetime


class CrmConflict(Exception):
    def __init__(self, field: str):
        self.field = field


class CrmReferenceError(Exception):
    def __init__(self, reference: str):
        self.reference = reference


class CrmRepository:
    _lead_fields = (
        "l.id,l.company_id,l.client_id,l.owner_id,u.name,l.name,l.company_name,l.email,"
        "l.phone,l.source::text,l.status::text,l.notes,l.created_at,l.updated_at"
    )
    _lead_joins = (
        " FROM leads l JOIN employees e ON e.id=l.owner_id JOIN users u ON u.id=e.user_id "
    )
    _opportunity_fields = (
        "o.id,o.company_id,o.client_id,c.name,o.lead_id,o.owner_id,u.name,o.name,"
        "o.description,o.value,o.currency,o.stage::text,o.status::text,"
        "o.expected_close_date,o.created_at,o.updated_at"
    )
    _opportunity_joins = (
        " FROM opportunities o JOIN clients c ON c.id=o.client_id "
        "JOIN employees e ON e.id=o.owner_id JOIN users u ON u.id=e.user_id "
    )
    _lead_columns = {
        "client_id",
        "owner_id",
        "name",
        "company_name",
        "email",
        "phone",
        "source",
        "status",
        "notes",
    }
    _opportunity_columns = {
        "client_id",
        "lead_id",
        "owner_id",
        "name",
        "description",
        "value",
        "currency",
        "stage",
        "status",
        "expected_close_date",
    }

    def list_options(
        self, company_id: UUID
    ) -> tuple[list[tuple[UUID, str]], list[tuple[UUID, str]]]:
        """Return only active, same-tenant CRM relationship choices."""
        with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT e.id,u.name FROM employees e "
                "JOIN users u ON u.id=e.user_id "
                "WHERE e.company_id=%s AND e.status='ACTIVE' AND u.status='ACTIVE' "
                "ORDER BY u.name,e.id",
                (company_id,),
            )
            owners = list(cursor.fetchall())
            cursor.execute(
                "SELECT id,name FROM clients WHERE company_id=%s AND status='ACTIVE' "
                "ORDER BY name,id",
                (company_id,),
            )
            clients = list(cursor.fetchall())
            return owners, clients

    def list_leads(
        self, company_id: UUID, filters: LeadListFilters
    ) -> tuple[tuple[LeadRecord, ...], int]:
        clauses = ["l.company_id=%s"]
        values: list[object] = [company_id]
        if filters.search:
            clauses.append("(l.name ILIKE %s OR l.company_name ILIKE %s OR l.email ILIKE %s)")
            pattern = f"%{filters.search}%"
            values.extend((pattern, pattern, pattern))
        for column, value in (
            ("l.status", filters.status),
            ("l.source", filters.source),
            ("l.owner_id", filters.owner_id),
        ):
            if value is not None:
                clauses.append(f"{column}=%s")
                values.append(value)
        where = " AND ".join(clauses)
        with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
            cursor.execute(f"SELECT COUNT(*){self._lead_joins}WHERE {where}", values)
            total_row = cursor.fetchone()
            total = int(total_row[0]) if total_row else 0
            cursor.execute(
                f"SELECT {self._lead_fields}{self._lead_joins}WHERE {where} "
                "ORDER BY l.created_at DESC,l.id LIMIT %s OFFSET %s",
                (*values, filters.page_size, (filters.page - 1) * filters.page_size),
            )
            return tuple(LeadRecord(*row) for row in cursor.fetchall()), total

    def get_lead(self, company_id: UUID, lead_id: UUID) -> LeadRecord | None:
        with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
            return self._get_lead(cursor, company_id, lead_id)

    def create_lead(
        self, company_id: UUID, actor_id: UUID, values: dict[str, object]
    ) -> LeadRecord:
        normalized = self._allowed(values, self._lead_columns)
        try:
            with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
                self._validate_owner(cursor, company_id, normalized.get("owner_id"))
                self._validate_client(cursor, company_id, normalized.get("client_id"))
                lead_id = uuid4()
                columns = ["id", "company_id", *normalized]
                params = [lead_id, company_id, *normalized.values()]
                placeholders = ",".join(["%s"] * len(columns))
                cursor.execute(
                    f"INSERT INTO leads({','.join(columns)}) VALUES({placeholders})",
                    params,
                )
                self._audit(
                    cursor,
                    company_id,
                    actor_id,
                    "LEAD",
                    lead_id,
                    "LEAD_CREATED",
                    {"name": normalized.get("name"), "source": normalized.get("source")},
                )
                record = self._get_lead(cursor, company_id, lead_id)
                if record is None:
                    raise RuntimeError("Lead insert returned no record.")
                return record
        except UniqueViolation as error:
            raise CrmConflict("email") from error

    def update_lead(
        self,
        company_id: UUID,
        actor_id: UUID,
        lead_id: UUID,
        values: dict[str, object],
    ) -> LeadRecord | None:
        normalized = self._allowed(values, self._lead_columns)
        try:
            with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
                cursor.execute(
                    "SELECT owner_id,client_id FROM leads WHERE id=%s AND company_id=%s FOR UPDATE",
                    (lead_id, company_id),
                )
                current = cursor.fetchone()
                if current is None:
                    return None
                owner_id = normalized.get("owner_id", current[0])
                client_id = normalized.get("client_id", current[1])
                self._validate_owner(cursor, company_id, owner_id)
                self._validate_client(cursor, company_id, client_id)
                setters = ",".join(f"{column}=%s" for column in normalized)
                cursor.execute(
                    f"UPDATE leads SET {setters},updated_at=NOW() WHERE id=%s AND company_id=%s",
                    (*normalized.values(), lead_id, company_id),
                )
                self._audit(
                    cursor,
                    company_id,
                    actor_id,
                    "LEAD",
                    lead_id,
                    "LEAD_UPDATED",
                    {"changed_fields": sorted(normalized)},
                )
                return self._get_lead(cursor, company_id, lead_id)
        except UniqueViolation as error:
            raise CrmConflict("email") from error

    def list_opportunities(
        self, company_id: UUID, filters: OpportunityListFilters
    ) -> tuple[tuple[OpportunityRecord, ...], int]:
        clauses = ["o.company_id=%s"]
        values: list[object] = [company_id]
        if filters.search:
            clauses.append("(o.name ILIKE %s OR o.description ILIKE %s OR c.name ILIKE %s)")
            pattern = f"%{filters.search}%"
            values.extend((pattern, pattern, pattern))
        for column, value in (
            ("o.stage", filters.stage),
            ("o.status", filters.status),
            ("o.owner_id", filters.owner_id),
            ("o.client_id", filters.client_id),
            ("o.lead_id", filters.lead_id),
        ):
            if value is not None:
                clauses.append(f"{column}=%s")
                values.append(value)
        where = " AND ".join(clauses)
        with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
            cursor.execute(f"SELECT COUNT(*){self._opportunity_joins}WHERE {where}", values)
            total_row = cursor.fetchone()
            total = int(total_row[0]) if total_row else 0
            cursor.execute(
                f"SELECT {self._opportunity_fields}{self._opportunity_joins}WHERE {where} "
                "ORDER BY o.created_at DESC,o.id LIMIT %s OFFSET %s",
                (*values, filters.page_size, (filters.page - 1) * filters.page_size),
            )
            return tuple(OpportunityRecord(*row) for row in cursor.fetchall()), total

    def get_opportunity(self, company_id: UUID, opportunity_id: UUID) -> OpportunityRecord | None:
        with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
            return self._get_opportunity(cursor, company_id, opportunity_id)

    def create_opportunity(
        self, company_id: UUID, actor_id: UUID, values: dict[str, object]
    ) -> OpportunityRecord:
        normalized = self._allowed(values, self._opportunity_columns)
        normalized["status"] = self._opportunity_status(str(normalized.get("stage", "NEW")))
        with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
            self._validate_owner(cursor, company_id, normalized.get("owner_id"))
            self._validate_client(cursor, company_id, normalized.get("client_id"), required=True)
            self._validate_lead_client(
                cursor,
                company_id,
                normalized.get("lead_id"),
                normalized.get("client_id"),
            )
            opportunity_id = uuid4()
            columns = ["id", "company_id", *normalized]
            params = [opportunity_id, company_id, *normalized.values()]
            placeholders = ",".join(["%s"] * len(columns))
            cursor.execute(
                f"INSERT INTO opportunities({','.join(columns)}) VALUES({placeholders})",
                params,
            )
            self._audit(
                cursor,
                company_id,
                actor_id,
                "OPPORTUNITY",
                opportunity_id,
                "OPPORTUNITY_CREATED",
                {"name": normalized.get("name"), "stage": normalized.get("stage")},
            )
            record = self._get_opportunity(cursor, company_id, opportunity_id)
            if record is None:
                raise RuntimeError("Opportunity insert returned no record.")
            return record

    def update_opportunity(
        self,
        company_id: UUID,
        actor_id: UUID,
        opportunity_id: UUID,
        values: dict[str, object],
    ) -> OpportunityRecord | None:
        normalized = self._allowed(values, self._opportunity_columns)
        with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT client_id,lead_id,owner_id,stage::text FROM opportunities "
                "WHERE id=%s AND company_id=%s FOR UPDATE",
                (opportunity_id, company_id),
            )
            current = cursor.fetchone()
            if current is None:
                return None
            client_id = normalized.get("client_id", current[0])
            lead_id = normalized.get("lead_id", current[1])
            owner_id = normalized.get("owner_id", current[2])
            stage = str(normalized.get("stage", current[3]))
            self._validate_owner(cursor, company_id, owner_id)
            self._validate_client(cursor, company_id, client_id, required=True)
            self._validate_lead_client(cursor, company_id, lead_id, client_id)
            normalized["status"] = self._opportunity_status(stage)
            setters = ",".join(f"{column}=%s" for column in normalized)
            cursor.execute(
                f"UPDATE opportunities SET {setters},updated_at=NOW() "
                "WHERE id=%s AND company_id=%s",
                (*normalized.values(), opportunity_id, company_id),
            )
            self._audit(
                cursor,
                company_id,
                actor_id,
                "OPPORTUNITY",
                opportunity_id,
                "OPPORTUNITY_UPDATED",
                {"changed_fields": sorted(normalized)},
            )
            return self._get_opportunity(cursor, company_id, opportunity_id)

    def _get_lead(self, cursor: Any, company_id: UUID, lead_id: UUID) -> LeadRecord | None:
        cursor.execute(
            f"SELECT {self._lead_fields}{self._lead_joins}WHERE l.id=%s AND l.company_id=%s",
            (lead_id, company_id),
        )
        row = cursor.fetchone()
        return LeadRecord(*row) if row else None

    def _get_opportunity(
        self, cursor: Any, company_id: UUID, opportunity_id: UUID
    ) -> OpportunityRecord | None:
        cursor.execute(
            f"SELECT {self._opportunity_fields}{self._opportunity_joins}"
            "WHERE o.id=%s AND o.company_id=%s",
            (opportunity_id, company_id),
        )
        row = cursor.fetchone()
        return OpportunityRecord(*row) if row else None

    @staticmethod
    def _validate_owner(cursor: Any, company_id: UUID, owner_id: object) -> None:
        cursor.execute(
            "SELECT 1 FROM employees WHERE id=%s AND company_id=%s AND status='ACTIVE'",
            (owner_id, company_id),
        )
        if cursor.fetchone() is None:
            raise CrmReferenceError("owner")

    @staticmethod
    def _validate_client(
        cursor: Any, company_id: UUID, client_id: object, *, required: bool = False
    ) -> None:
        if client_id is None and not required:
            return
        cursor.execute(
            "SELECT 1 FROM clients WHERE id=%s AND company_id=%s",
            (client_id, company_id),
        )
        if cursor.fetchone() is None:
            raise CrmReferenceError("client")

    @staticmethod
    def _validate_lead_client(
        cursor: Any, company_id: UUID, lead_id: object, client_id: object
    ) -> None:
        if lead_id is None:
            return
        cursor.execute(
            "SELECT client_id FROM leads WHERE id=%s AND company_id=%s",
            (lead_id, company_id),
        )
        row = cursor.fetchone()
        if row is None:
            raise CrmReferenceError("lead")
        if row[0] is not None and row[0] != client_id:
            raise CrmReferenceError("lead_client")

    @staticmethod
    def _opportunity_status(stage: str) -> str:
        return "CLOSED" if stage in {"WON", "LOST"} else "OPEN"

    @staticmethod
    def _allowed(values: dict[str, object], allowed: set[str]) -> dict[str, object]:
        return {key: value for key, value in values.items() if key in allowed}

    @staticmethod
    def _audit(
        cursor: Any,
        company_id: UUID,
        actor_id: UUID,
        entity_type: str,
        entity_id: UUID,
        action: str,
        details: dict[str, object],
    ) -> None:
        cursor.execute(
            "INSERT INTO crm_audits(id,company_id,actor_id,entity_type,entity_id,action,details,created_at) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb,NOW())",
            (
                uuid4(),
                company_id,
                actor_id,
                entity_type,
                entity_id,
                action,
                json.dumps(details, default=str),
            ),
        )

    def is_ready(self) -> bool:
        try:
            with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
                cursor.execute(
                    "SELECT to_regclass('public.leads') IS NOT NULL AND "
                    "to_regclass('public.opportunities') IS NOT NULL AND "
                    "to_regclass('public.crm_audits') IS NOT NULL"
                )
                row = cursor.fetchone()
                return bool(row and row[0])
        except Exception:
            return False
