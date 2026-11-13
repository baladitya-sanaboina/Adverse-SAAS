import json
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, TypeVar
from uuid import UUID, uuid4

from psycopg.errors import UniqueViolation

from app.database.connectivity import database_pool

RecordT = TypeVar("RecordT")


@dataclass(frozen=True)
class DepartmentRecord:
    id: UUID
    name: str
    description: str
    status: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class BranchRecord:
    id: UUID
    name: str
    code: str
    address: str
    city: str
    state: str
    country: str
    status: str
    created_at: datetime
    updated_at: datetime


class OrganizationConflict(Exception):
    pass


class OrganizationRepository:
    _department_fields = "id,name,description,status::text,created_at,updated_at"
    _branch_fields = "id,name,code,address,city,state,country,status::text,created_at,updated_at"

    def list_departments(
        self, company_id: UUID, search: str, status: str | None
    ) -> tuple[DepartmentRecord, ...]:
        query = f"SELECT {self._department_fields} FROM departments WHERE company_id=%s"
        values: list[object] = [company_id]
        if search:
            query += " AND (name ILIKE %s OR description ILIKE %s)"
            values.extend([f"%{search}%", f"%{search}%"])
        if status:
            query += " AND status=%s"
            values.append(status)
        query += " ORDER BY name"
        with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
            cursor.execute(query, values)
            return tuple(DepartmentRecord(*row) for row in cursor.fetchall())

    def list_branches(
        self, company_id: UUID, search: str, status: str | None
    ) -> tuple[BranchRecord, ...]:
        query = f"SELECT {self._branch_fields} FROM branches WHERE company_id=%s"
        values: list[object] = [company_id]
        if search:
            query += " AND (name ILIKE %s OR code ILIKE %s OR city ILIKE %s)"
            values.extend([f"%{search}%"] * 3)
        if status:
            query += " AND status=%s"
            values.append(status)
        query += " ORDER BY name"
        with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
            cursor.execute(query, values)
            return tuple(BranchRecord(*row) for row in cursor.fetchall())

    def get_department(self, company_id: UUID, item_id: UUID) -> DepartmentRecord | None:
        return self._get(
            "departments", self._department_fields, DepartmentRecord, company_id, item_id
        )

    def get_branch(self, company_id: UUID, item_id: UUID) -> BranchRecord | None:
        return self._get("branches", self._branch_fields, BranchRecord, company_id, item_id)

    def _get(
        self,
        table: str,
        fields: str,
        record_type: Callable[..., RecordT],
        company_id: UUID,
        item_id: UUID,
    ) -> RecordT | None:
        with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
            cursor.execute(
                f"SELECT {fields} FROM {table} WHERE id=%s AND company_id=%s", (item_id, company_id)
            )
            row = cursor.fetchone()
            return record_type(*row) if row else None

    def create_department(self, company_id: UUID, name: str, description: str) -> DepartmentRecord:
        record = self._write(
            "departments",
            self._department_fields,
            DepartmentRecord,
            company_id,
            None,
            {"name": name, "description": description},
        )
        if record is None:
            raise RuntimeError("Department insert returned no record.")
        return record

    def create_branch(self, company_id: UUID, values: dict[str, object]) -> BranchRecord:
        record = self._write(
            "branches", self._branch_fields, BranchRecord, company_id, None, values
        )
        if record is None:
            raise RuntimeError("Branch insert returned no record.")
        return record

    def update_department(
        self, company_id: UUID, item_id: UUID, values: dict[str, object]
    ) -> DepartmentRecord | None:
        return self._write(
            "departments", self._department_fields, DepartmentRecord, company_id, item_id, values
        )

    def update_branch(
        self, company_id: UUID, item_id: UUID, values: dict[str, object]
    ) -> BranchRecord | None:
        return self._write(
            "branches", self._branch_fields, BranchRecord, company_id, item_id, values
        )

    def write_audit(
        self,
        action: str,
        actor_id: UUID,
        company_id: UUID,
        entity_type: str,
        entity_id: UUID,
        details: dict[str, object],
    ) -> None:
        with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
            cursor.execute(
                'INSERT INTO "organization_audits" '
                "(id,action,actor_id,company_id,entity_type,entity_id,details,created_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,NOW())",
                (
                    uuid4(),
                    action,
                    actor_id,
                    company_id,
                    entity_type,
                    entity_id,
                    json.dumps(details),
                ),
            )

    def _write(
        self,
        table: str,
        fields: str,
        record_type: Callable[..., RecordT],
        company_id: UUID,
        item_id: UUID | None,
        values: dict[str, object],
    ) -> RecordT | None:
        try:
            with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
                if item_id is None:
                    columns = ["id", "company_id", *values]
                    params = [uuid4(), company_id, *values.values()]
                    placeholders = ",".join(["%s"] * len(columns))
                    cursor.execute(
                        f"INSERT INTO {table} ({','.join(columns)}) VALUES ({placeholders}) RETURNING {fields}",
                        params,
                    )
                else:
                    if not values:
                        return self._get(table, fields, record_type, company_id, item_id)
                    setters = ",".join(f"{key}=%s" for key in values)
                    cursor.execute(
                        f"UPDATE {table} SET {setters},updated_at=NOW() WHERE id=%s AND company_id=%s RETURNING {fields}",
                        [*values.values(), item_id, company_id],
                    )
                row = cursor.fetchone()
                return record_type(*row) if row else None
        except UniqueViolation as error:
            raise OrganizationConflict from error

    def is_ready(self) -> bool:
        try:
            with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
                cursor.execute(
                    "SELECT to_regclass('public.departments') IS NOT NULL AND to_regclass('public.branches') IS NOT NULL"
                )
                row = cursor.fetchone()
                return bool(row and row[0])
        except Exception:
            return False
