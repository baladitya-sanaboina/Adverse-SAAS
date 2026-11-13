import json
from dataclasses import dataclass
from uuid import UUID, uuid4

from app.database.connectivity import database_pool


@dataclass(frozen=True)
class CompanyUserRecord:
    id: UUID
    name: str
    email: str
    status: str
    role_id: UUID
    role_name: str
    role_code: str
    department_id: UUID | None
    department_name: str | None
    branch_id: UUID | None
    branch_name: str | None


class UserAssignmentRepository:
    _fields = "u.id,u.name,u.email,u.status::text,r.id,r.name,r.code," "d.id,d.name,b.id,b.name"

    def list_users(self, company_id: UUID) -> tuple[CompanyUserRecord, ...]:
        with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
            cursor.execute(
                f"SELECT {self._fields} FROM users u JOIN roles r ON r.id=u.role_id "
                "LEFT JOIN departments d ON d.id=u.department_id LEFT JOIN branches b ON b.id=u.branch_id "
                "WHERE u.company_id=%s ORDER BY u.name,u.email",
                (company_id,),
            )
            return tuple(CompanyUserRecord(*row) for row in cursor.fetchall())

    def options(
        self, company_id: UUID
    ) -> tuple[list[tuple[UUID, str]], list[tuple[UUID, str]], list[tuple[UUID, str]]]:
        with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT id,name FROM roles WHERE status='ACTIVE' AND "
                "(company_id=%s OR (is_system=true AND code IN "
                "('COMPANY_ADMIN','COMPANY_MANAGER','COMPANY_EMPLOYEE','COMPANY_CLIENT'))) ORDER BY name",
                (company_id,),
            )
            roles = list(cursor.fetchall())
            cursor.execute(
                "SELECT id,name FROM departments WHERE company_id=%s AND status='ACTIVE' ORDER BY name",
                (company_id,),
            )
            departments = list(cursor.fetchall())
            cursor.execute(
                "SELECT id,name FROM branches WHERE company_id=%s AND status='ACTIVE' ORDER BY name",
                (company_id,),
            )
            branches = list(cursor.fetchall())
            return roles, departments, branches

    def assign(
        self,
        company_id: UUID,
        user_id: UUID,
        actor_id: UUID,
        role_id: UUID,
        department_id: UUID | None,
        branch_id: UUID | None,
    ) -> CompanyUserRecord | None:
        with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT role_id,department_id,branch_id FROM users WHERE id=%s AND company_id=%s FOR UPDATE",
                (user_id, company_id),
            )
            previous = cursor.fetchone()
            if not previous:
                return None
            cursor.execute(
                "SELECT id FROM roles WHERE id=%s AND status='ACTIVE' AND "
                "(company_id=%s OR (is_system=true AND code IN "
                "('COMPANY_ADMIN','COMPANY_MANAGER','COMPANY_EMPLOYEE','COMPANY_CLIENT')))",
                (role_id, company_id),
            )
            if not cursor.fetchone():
                return None
            for table, value in (("departments", department_id), ("branches", branch_id)):
                if value is not None:
                    cursor.execute(
                        f"SELECT id FROM {table} WHERE id=%s AND company_id=%s AND status='ACTIVE'",
                        (value, company_id),
                    )
                    if not cursor.fetchone():
                        return None
            cursor.execute(
                "UPDATE users SET role_id=%s,department_id=%s,branch_id=%s,updated_at=NOW() WHERE id=%s",
                (role_id, department_id, branch_id, user_id),
            )
            cursor.execute(
                "UPDATE employees SET role_id=%s,department_id=%s,branch_id=%s,updated_at=NOW() "
                "WHERE user_id=%s AND company_id=%s",
                (role_id, department_id, branch_id, user_id, company_id),
            )
            names = ("ROLE", "DEPARTMENT", "BRANCH")
            for index, (old, new) in enumerate(zip(previous, (role_id, department_id, branch_id))):
                if old != new:
                    action = f"USER_{names[index]}_{'ASSIGNED' if old is None else 'CHANGED'}"
                    cursor.execute(
                        "INSERT INTO organization_audits(id,action,actor_id,company_id,entity_type,entity_id,details,created_at) VALUES(%s,%s,%s,%s,'USER',%s,%s::jsonb,NOW())",
                        (
                            uuid4(),
                            action,
                            actor_id,
                            company_id,
                            user_id,
                            json.dumps(
                                {
                                    "previous_id": str(old) if old else None,
                                    "new_id": str(new) if new else None,
                                }
                            ),
                        ),
                    )
            cursor.execute(
                f"SELECT {self._fields} FROM users u JOIN roles r ON r.id=u.role_id LEFT JOIN departments d ON d.id=u.department_id LEFT JOIN branches b ON b.id=u.branch_id WHERE u.id=%s AND u.company_id=%s",
                (user_id, company_id),
            )
            row = cursor.fetchone()
            return CompanyUserRecord(*row) if row else None

    def is_ready(self) -> bool:
        try:
            with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
                cursor.execute(
                    "SELECT column_name FROM information_schema.columns WHERE table_name='users' AND column_name IN ('department_id','branch_id')"
                )
                return len(cursor.fetchall()) == 2
        except Exception:
            return False
