import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from psycopg.errors import ForeignKeyViolation, UniqueViolation

from app.database.connectivity import database_pool
from app.schemas.employee import EmployeeListFilters


@dataclass(frozen=True)
class EmployeeRecord:
    id: UUID
    company_id: UUID
    user_id: UUID
    user_name: str
    user_email: str
    first_name: str | None
    last_name: str | None
    phone_number: str | None
    user_status: str
    employee_code: str
    department_id: UUID | None
    department_name: str | None
    branch_id: UUID | None
    branch_name: str | None
    role_id: UUID
    role_name: str
    role_code: str
    status: str
    created_at: datetime
    updated_at: datetime


class EmployeeConflict(Exception):
    def __init__(self, field: str):
        self.field = field


class EmployeeReferenceError(Exception):
    def __init__(self, reference: str):
        self.reference = reference


class EmployeeDeletionError(Exception):
    def __init__(self, reason: str):
        self.reason = reason


class EmployeeRepository:
    _fields = (
        "e.id,e.company_id,e.user_id,u.name,u.email,u.first_name,u.last_name,u.phone_number,u.status::text,e.employee_code,"
        "e.department_id,d.name,e.branch_id,b.name,e.role_id,r.name,r.code,"
        "e.status::text,e.created_at,e.updated_at"
    )
    _joins = (
        " FROM employees e JOIN users u ON u.id=e.user_id "
        "LEFT JOIN departments d ON d.id=e.department_id LEFT JOIN branches b ON b.id=e.branch_id "
        "JOIN roles r ON r.id=e.role_id "
    )

    def list(
        self, company_id: UUID, filters: EmployeeListFilters
    ) -> tuple[tuple[EmployeeRecord, ...], int]:
        clauses = ["e.company_id=%s"]
        values: list[object] = [company_id]
        if filters.search:
            clauses.append("(u.name ILIKE %s OR u.email ILIKE %s OR e.employee_code ILIKE %s)")
            pattern = f"%{filters.search}%"
            values.extend((pattern, pattern, pattern))
        for column, value in (
            ("e.status", filters.status),
            ("e.department_id", filters.department_id),
            ("e.branch_id", filters.branch_id),
            ("e.role_id", filters.role_id),
        ):
            if value is not None:
                clauses.append(f"{column}=%s")
                values.append(value)
        where = " AND ".join(clauses)
        with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
            cursor.execute(f"SELECT COUNT(*){self._joins}WHERE {where}", values)
            total_row = cursor.fetchone()
            total = int(total_row[0]) if total_row else 0
            cursor.execute(
                f"SELECT {self._fields}{self._joins}WHERE {where} "
                "ORDER BY e.employee_code LIMIT %s OFFSET %s",
                (*values, filters.page_size, (filters.page - 1) * filters.page_size),
            )
            return tuple(EmployeeRecord(*row) for row in cursor.fetchall()), total

    def get(self, company_id: UUID, employee_id: UUID) -> EmployeeRecord | None:
        with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
            return self._get(cursor, company_id, employee_id)

    def create(
        self,
        company_id: UUID,
        actor_id: UUID,
        user_id: UUID,
        employee_code: str,
        department_id: UUID,
        branch_id: UUID,
        role_id: UUID,
        status: str,
    ) -> EmployeeRecord:
        try:
            with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
                self._validate_user(cursor, company_id, user_id)
                self._validate_assignment(cursor, company_id, department_id, branch_id, role_id)
                employee_id = uuid4()
                cursor.execute(
                    "INSERT INTO employees(id,company_id,user_id,employee_code,department_id,branch_id,role_id,status,created_at,updated_at) "
                    "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,NOW(),NOW())",
                    (
                        employee_id,
                        company_id,
                        user_id,
                        employee_code,
                        department_id,
                        branch_id,
                        role_id,
                        status,
                    ),
                )
                cursor.execute(
                    "UPDATE users SET department_id=%s,branch_id=%s,role_id=%s,updated_at=NOW() "
                    "WHERE id=%s AND company_id=%s",
                    (department_id, branch_id, role_id, user_id, company_id),
                )
                self._audit(
                    cursor,
                    "EMPLOYEE_CREATED",
                    employee_id,
                    company_id,
                    actor_id,
                    {"employee_code": employee_code, "user_id": str(user_id)},
                )
                record = self._get(cursor, company_id, employee_id)
                if record is None:
                    raise RuntimeError("Employee insert returned no record.")
                return record
        except UniqueViolation as error:
            constraint = error.diag.constraint_name or ""
            raise EmployeeConflict(
                "user" if "user_id" in constraint else "employee_code"
            ) from error

    def update(
        self,
        company_id: UUID,
        actor_id: UUID,
        employee_id: UUID,
        values: dict[str, object],
    ) -> EmployeeRecord | None:
        try:
            with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
                cursor.execute(
                    "SELECT e.user_id,e.department_id,e.branch_id,e.role_id,u.first_name,u.last_name,u.name "
                    "FROM employees e JOIN users u ON u.id=e.user_id "
                    "WHERE e.id=%s AND e.company_id=%s FOR UPDATE",
                    (employee_id, company_id),
                )
                current = cursor.fetchone()
                if current is None:
                    return None
                (
                    user_id,
                    current_department,
                    current_branch,
                    current_role,
                    current_first_name,
                    current_last_name,
                    current_name,
                ) = current
                department_id = values.get("department_id", current_department)
                branch_id = values.get("branch_id", current_branch)
                role_id = values.get("role_id", current_role)
                self._validate_assignment(cursor, company_id, department_id, branch_id, role_id)
                employee_values = {
                    field: value
                    for field, value in values.items()
                    if field in {"employee_code", "department_id", "branch_id", "role_id", "status"}
                }
                if employee_values:
                    setters = ",".join(f"{field}=%s" for field in employee_values)
                    cursor.execute(
                        f"UPDATE employees SET {setters},updated_at=NOW() WHERE id=%s AND company_id=%s",
                        [*employee_values.values(), employee_id, company_id],
                    )
                identity_changed = {"first_name", "last_name", "phone_number"}.intersection(values)
                assignment_changed = {"department_id", "branch_id", "role_id"}.intersection(values)
                if identity_changed or assignment_changed:
                    first_name = values.get("first_name", current_first_name)
                    last_name = values.get("last_name", current_last_name)
                    display_name = (
                        " ".join(
                            part.strip()
                            for part in (first_name, last_name)
                            if isinstance(part, str) and part.strip()
                        )
                        or current_name
                    )
                    cursor.execute(
                        "UPDATE users SET first_name=%s,last_name=%s,phone_number=%s,name=%s,"
                        "department_id=%s,branch_id=%s,role_id=%s,updated_at=NOW() "
                        "WHERE id=%s AND company_id=%s",
                        (
                            first_name,
                            last_name,
                            (
                                values.get("phone_number")
                                if "phone_number" in values
                                else self._phone(cursor, user_id)
                            ),
                            display_name,
                            department_id,
                            branch_id,
                            role_id,
                            user_id,
                            company_id,
                        ),
                    )
                self._audit(
                    cursor,
                    "EMPLOYEE_UPDATED",
                    employee_id,
                    company_id,
                    actor_id,
                    {"changed_fields": sorted(values)},
                )
                return self._get(cursor, company_id, employee_id)
        except UniqueViolation as error:
            raise EmployeeConflict("employee_code") from error

    def delete_pending(self, company_id: UUID, employee_id: UUID) -> tuple[str, str] | None:
        try:
            with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
                cursor.execute(
                    "SELECT e.user_id,u.name,u.email,u.status::text FROM employees e "
                    'JOIN "users" u ON u.id=e.user_id '
                    "WHERE e.company_id=%s AND e.id=%s FOR UPDATE",
                    (company_id, employee_id),
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                user_id, user_name, user_email, user_status = row
                if user_status != "PENDING_VERIFICATION":
                    raise EmployeeDeletionError("ACTIVE_ACCOUNT")
                cursor.execute(
                    "UPDATE registration_audits SET created_user_id=NULL WHERE created_user_id=%s",
                    (user_id,),
                )
                cursor.execute(
                    "DELETE FROM company_invitations WHERE company_id=%s AND user_id=%s",
                    (company_id, user_id),
                )
                cursor.execute(
                    "DELETE FROM employees WHERE id=%s AND company_id=%s RETURNING id",
                    (employee_id, company_id),
                )
                if cursor.fetchone() is None:
                    return None
                cursor.execute(
                    'DELETE FROM "users" WHERE id=%s AND company_id=%s AND status=%s RETURNING id',
                    (user_id, company_id, "PENDING_VERIFICATION"),
                )
                if cursor.fetchone() is None:
                    raise EmployeeDeletionError("ACTIVE_ACCOUNT")
                return user_name, user_email
        except ForeignKeyViolation as error:
            raise EmployeeDeletionError("IN_USE") from error

    @staticmethod
    def _validate_user(cursor: Any, company_id: UUID, user_id: UUID) -> None:
        cursor.execute(
            "SELECT 1 FROM users WHERE id=%s AND company_id=%s AND status IN ('ACTIVE','PENDING_VERIFICATION')",
            (user_id, company_id),
        )
        if cursor.fetchone() is None:
            raise EmployeeReferenceError("user")

    @staticmethod
    def _validate_assignment(
        cursor: Any,
        company_id: UUID,
        department_id: object,
        branch_id: object,
        role_id: object,
    ) -> None:
        for table, value, reference in (
            ("departments", department_id, "department"),
            ("branches", branch_id, "branch"),
        ):
            if value is None:
                continue
            cursor.execute(
                f"SELECT 1 FROM {table} WHERE id=%s AND company_id=%s AND status='ACTIVE'",
                (value, company_id),
            )
            if cursor.fetchone() is None:
                raise EmployeeReferenceError(reference)
        cursor.execute(
            "SELECT 1 FROM roles WHERE id=%s AND status='ACTIVE' AND "
            "(company_id=%s OR (is_system=true AND code IN ('COMPANY_ADMIN','COMPANY_MANAGER','COMPANY_EMPLOYEE','COMPANY_CLIENT')))",
            (role_id, company_id),
        )
        if cursor.fetchone() is None:
            raise EmployeeReferenceError("role")

    def _get(self, cursor: Any, company_id: UUID, employee_id: UUID) -> EmployeeRecord | None:
        cursor.execute(
            f"SELECT {self._fields}{self._joins}WHERE e.id=%s AND e.company_id=%s",
            (employee_id, company_id),
        )
        row = cursor.fetchone()
        return EmployeeRecord(*row) if row else None

    @staticmethod
    def _phone(cursor: Any, user_id: UUID) -> str | None:
        cursor.execute("SELECT phone_number FROM users WHERE id=%s", (user_id,))
        row = cursor.fetchone()
        return row[0] if row else None

    @staticmethod
    def _audit(
        cursor: Any,
        action: str,
        employee_id: UUID,
        company_id: UUID,
        actor_id: UUID,
        details: dict[str, object],
    ) -> None:
        cursor.execute(
            "INSERT INTO employee_audits(id,employee_id,company_id,actor_id,action,details,created_at) "
            "VALUES(%s,%s,%s,%s,%s,%s::jsonb,NOW())",
            (uuid4(), employee_id, company_id, actor_id, action, json.dumps(details)),
        )

    def is_ready(self) -> bool:
        try:
            with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
                cursor.execute(
                    "SELECT to_regclass('public.employees') IS NOT NULL AND "
                    "to_regclass('public.employee_audits') IS NOT NULL"
                )
                row = cursor.fetchone()
                return bool(row and row[0])
        except Exception:
            return False
