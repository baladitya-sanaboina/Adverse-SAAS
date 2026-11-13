import json
import re
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from psycopg.errors import UniqueViolation

from app.database.connectivity import database_pool


@dataclass(frozen=True)
class RoleRecord:
    id: UUID
    name: str
    code: str
    description: str
    status: str
    is_system: bool
    user_count: int
    permission_count: int
    created_at: datetime
    updated_at: datetime


class RoleConflict(Exception):
    pass


class RoleAssigned(Exception):
    pass


class RoleManagementRepository:
    _fields = (
        "r.id,r.name,r.code,r.description,r.status::text,r.is_system,"
        "COUNT(DISTINCT u.id)::int,COUNT(DISTINCT (rp.module_id,rp.permission_id))::int,"
        "r.created_at,r.updated_at"
    )
    _group = (
        " GROUP BY r.id,r.name,r.code,r.description,r.status,r.is_system,r.created_at,r.updated_at"
    )

    @staticmethod
    def _scope() -> str:
        return "(r.company_id=%s OR (r.is_system=true AND r.code IN ('COMPANY_ADMIN','COMPANY_MANAGER','COMPANY_EMPLOYEE','COMPANY_CLIENT')))"

    def list_roles(
        self, company_id: UUID, search: str, status: str | None
    ) -> tuple[RoleRecord, ...]:
        query = (
            f"SELECT {self._fields} FROM roles r "
            "LEFT JOIN users u ON u.role_id=r.id AND u.company_id=%s "
            "LEFT JOIN role_permissions rp ON rp.role_id=r.id WHERE " + self._scope()
        )
        values: list[object] = [company_id, company_id]
        if search:
            query += " AND (r.name ILIKE %s OR r.description ILIKE %s)"
            values.extend([f"%{search}%"] * 2)
        if status:
            query += " AND r.status=%s"
            values.append(status)
        query += self._group + " ORDER BY r.is_system DESC,r.name"
        with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
            cursor.execute(query, values)
            return tuple(RoleRecord(*row) for row in cursor.fetchall())

    def get_role(self, company_id: UUID, role_id: UUID) -> tuple[RoleRecord, list[str]] | None:
        query = (
            f"SELECT {self._fields} FROM roles r "
            "LEFT JOIN users u ON u.role_id=r.id AND u.company_id=%s "
            "LEFT JOIN role_permissions rp ON rp.role_id=r.id "
            "WHERE r.id=%s AND " + self._scope() + self._group
        )
        with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
            cursor.execute(query, (company_id, role_id, company_id))
            row = cursor.fetchone()
            if not row:
                return None
            cursor.execute(
                "SELECT m.code||'.'||p.code FROM role_permissions rp "
                "JOIN modules m ON m.id=rp.module_id JOIN permissions p ON p.id=rp.permission_id "
                "WHERE rp.role_id=%s ORDER BY m.name,p.name",
                (role_id,),
            )
            return RoleRecord(*row), [str(item[0]) for item in cursor.fetchall()]

    def permission_catalog(self) -> tuple[tuple[str, str, str, str], ...]:
        with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT m.code,m.name,p.code,p.name FROM modules m CROSS JOIN permissions p "
                "WHERE m.code NOT IN ('DEVELOPERS','COMPANIES','SUBSCRIPTIONS') "
                "ORDER BY m.name,p.name"
            )
            return tuple(cursor.fetchall())

    def valid_permission_keys(self) -> set[str]:
        return {f"{row[0]}.{row[2]}" for row in self.permission_catalog()}

    @staticmethod
    def _write_permissions(cursor: object, role_id: UUID, permissions: list[str]) -> None:
        cursor.execute("DELETE FROM role_permissions WHERE role_id=%s", (role_id,))  # type: ignore[attr-defined]
        for key in permissions:
            module, action = key.split(".", 1)
            cursor.execute(  # type: ignore[attr-defined]
                "INSERT INTO role_permissions(role_id,module_id,permission_id,created_at) "
                "SELECT %s,m.id,p.id,NOW() FROM modules m CROSS JOIN permissions p "
                "WHERE m.code=%s AND p.code=%s",
                (role_id, module, action),
            )

    @staticmethod
    def _audit(
        cursor: object,
        action: str,
        actor_id: UUID,
        company_id: UUID,
        role_id: UUID,
        details: dict[str, object],
    ) -> None:
        cursor.execute(  # type: ignore[attr-defined]
            "INSERT INTO organization_audits(id,action,actor_id,company_id,entity_type,entity_id,details,created_at) "
            "VALUES(%s,%s,%s,%s,'ROLE',%s,%s::jsonb,NOW())",
            (uuid4(), action, actor_id, company_id, role_id, json.dumps(details)),
        )

    def create(
        self, company_id: UUID, actor_id: UUID, name: str, description: str, permissions: list[str]
    ) -> UUID:
        slug = re.sub(r"[^A-Z0-9]+", "_", name.upper()).strip("_")[:32]
        code = f"COMPANY_EMPLOYEE__{company_id.hex[:8]}_{slug}_{uuid4().hex[:6]}"
        try:
            with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
                role_id = uuid4()
                cursor.execute(
                    "INSERT INTO roles(id,company_id,name,code,description,status,is_system,created_at,updated_at) "
                    "VALUES(%s,%s,%s,%s,%s,'ACTIVE',false,NOW(),NOW())",
                    (role_id, company_id, name, code, description),
                )
                self._write_permissions(cursor, role_id, permissions)
                self._audit(cursor, "ROLE_CREATED", actor_id, company_id, role_id, {"name": name})
                return role_id
        except UniqueViolation as error:
            raise RoleConflict from error

    def update(
        self, company_id: UUID, actor_id: UUID, role_id: UUID, values: dict[str, object]
    ) -> bool:
        try:
            with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
                cursor.execute(
                    "SELECT name FROM roles WHERE id=%s AND company_id=%s AND is_system=false FOR UPDATE",
                    (role_id, company_id),
                )
                previous = cursor.fetchone()
                if not previous:
                    return False
                permissions = values.pop("permissions", None)
                updates = {key: value for key, value in values.items() if value is not None}
                if updates:
                    columns = ",".join(f"{key}=%s" for key in updates)
                    cursor.execute(
                        f"UPDATE roles SET {columns},updated_at=NOW() WHERE id=%s",
                        (*updates.values(), role_id),
                    )
                if permissions is not None:
                    self._write_permissions(cursor, role_id, permissions)  # type: ignore[arg-type]
                    self._audit(
                        cursor,
                        "ROLE_PERMISSIONS_UPDATED",
                        actor_id,
                        company_id,
                        role_id,
                        {"permissions": permissions},
                    )
                if updates:
                    action = (
                        "ROLE_DISABLED"
                        if updates.get("status") == "INACTIVE"
                        else (
                            "ROLE_ACTIVATED"
                            if updates.get("status") == "ACTIVE"
                            else "ROLE_UPDATED"
                        )
                    )
                    self._audit(
                        cursor,
                        action,
                        actor_id,
                        company_id,
                        role_id,
                        {"changed_fields": list(updates)},
                    )
                return True
        except UniqueViolation as error:
            raise RoleConflict from error

    def delete(self, company_id: UUID, actor_id: UUID, role_id: UUID) -> bool:
        with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT name,(SELECT COUNT(*) FROM users WHERE role_id=r.id) FROM roles r "
                "WHERE r.id=%s AND r.company_id=%s AND r.is_system=false FOR UPDATE",
                (role_id, company_id),
            )
            row = cursor.fetchone()
            if not row:
                return False
            if int(row[1]):
                raise RoleAssigned
            self._audit(cursor, "ROLE_DELETED", actor_id, company_id, role_id, {"name": row[0]})
            cursor.execute("DELETE FROM roles WHERE id=%s", (role_id,))
            return True

    def is_ready(self) -> bool:
        try:
            with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
                cursor.execute(
                    "SELECT COUNT(*)=4 FROM information_schema.columns WHERE table_name='roles' "
                    "AND column_name IN ('company_id','description','status','is_system')"
                )
                row = cursor.fetchone()
                return bool(row and row[0])
        except Exception:
            return False
