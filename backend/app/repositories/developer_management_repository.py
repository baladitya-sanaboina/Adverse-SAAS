from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

from psycopg.errors import UniqueViolation

from app.database.connectivity import database_pool


@dataclass(frozen=True)
class DeveloperRecord:
    id: UUID
    first_name: str
    last_name: str
    name: str
    email: str
    phone: str
    status: str
    created_at: datetime
    updated_at: datetime
    last_login: datetime | None


@dataclass(frozen=True)
class PermissionRecord:
    module: str
    action: str


@dataclass(frozen=True)
class DeveloperAuditRecord:
    action: str
    actor_name: str
    details: str | None
    created_at: datetime


class DeveloperManagementRepository:
    def actor_is_platform_owner(self, actor_id: UUID) -> bool:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT EXISTS(SELECT 1 FROM \"users\" u JOIN \"roles\" r ON r.id=u.role_id WHERE u.id=%s AND u.status='ACTIVE' AND r.code='PLATFORM_OWNER')",
                    (actor_id,),
                )
                record = cursor.fetchone()
                return bool(record and record[0])

    def email_exists(self, email: str, exclude_id: UUID | None = None) -> bool:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    'SELECT EXISTS(SELECT 1 FROM "users" WHERE LOWER(email)=LOWER(%s) AND (%s::uuid IS NULL OR id<>%s))',
                    (email, exclude_id, exclude_id),
                )
                record = cursor.fetchone()
                return bool(record and record[0])

    def permission_catalog(self) -> tuple[PermissionRecord, ...]:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    'SELECT m.code,p.code FROM "modules" m CROSS JOIN "permissions" p ORDER BY m.code,p.code'
                )
                return tuple(PermissionRecord(*row) for row in cursor.fetchall())

    def default_permissions(self) -> tuple[PermissionRecord, ...]:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    'SELECT m.code,p.code FROM "role_permissions" rp JOIN "roles" r ON r.id=rp.role_id JOIN "modules" m ON m.id=rp.module_id JOIN "permissions" p ON p.id=rp.permission_id WHERE r.code=\'DEVELOPER\' ORDER BY m.code,p.code'
                )
                return tuple(PermissionRecord(*row) for row in cursor.fetchall())

    def list_developers(
        self,
        *,
        page: int,
        page_size: int,
        search: str,
        status: str | None,
        created_from: date | None,
        created_to: date | None,
        sort: str,
    ) -> tuple[tuple[DeveloperRecord, ...], int]:
        where = ["r.code='DEVELOPER'"]
        values: list[object] = []
        if search:
            where.append("(u.name ILIKE %s OR u.email ILIKE %s)")
            values.extend([f"%{search}%", f"%{search}%"])
        if status:
            where.append("u.status::text=%s")
            values.append(status)
        if created_from:
            where.append("u.created_at::date >= %s")
            values.append(created_from)
        if created_to:
            where.append("u.created_at::date <= %s")
            values.append(created_to)
        clause = " AND ".join(where)
        order = {"newest": "u.created_at DESC", "oldest": "u.created_at ASC", "a-z": "u.name ASC"}[
            sort
        ]
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f'SELECT COUNT(*) FROM "users" u JOIN "roles" r ON r.id=u.role_id WHERE {clause}',
                    values,
                )
                total_record = cursor.fetchone()
                cursor.execute(
                    f"SELECT u.id,COALESCE(u.first_name,split_part(u.name,' ',1)),COALESCE(u.last_name,NULLIF(substring(u.name from position(' ' in u.name)+1),u.name),''),u.name,u.email,COALESCE(u.phone_number,''),u.status::text,u.created_at,u.updated_at,(SELECT MAX(s.login_at) FROM auth_sessions s WHERE s.user_id=u.id) FROM \"users\" u JOIN \"roles\" r ON r.id=u.role_id WHERE {clause} ORDER BY {order} LIMIT %s OFFSET %s",
                    [*values, page_size, (page - 1) * page_size],
                )
                return tuple(DeveloperRecord(*row) for row in cursor.fetchall()), int(
                    total_record[0] if total_record else 0
                )

    def get_developer(self, developer_id: UUID) -> DeveloperRecord | None:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT u.id,COALESCE(u.first_name,split_part(u.name,' ',1)),COALESCE(u.last_name,''),u.name,u.email,COALESCE(u.phone_number,''),u.status::text,u.created_at,u.updated_at,(SELECT MAX(s.login_at) FROM auth_sessions s WHERE s.user_id=u.id) FROM \"users\" u JOIN \"roles\" r ON r.id=u.role_id WHERE u.id=%s AND r.code='DEVELOPER'",
                    (developer_id,),
                )
                row = cursor.fetchone()
                return DeveloperRecord(*row) if row else None

    def permissions_for(self, developer_id: UUID) -> tuple[PermissionRecord, ...]:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT m.code,p.code FROM user_permissions up JOIN modules m ON m.id=up.module_id JOIN permissions p ON p.id=up.permission_id WHERE up.user_id=%s ORDER BY m.code,p.code",
                    (developer_id,),
                )
                return tuple(PermissionRecord(*row) for row in cursor.fetchall())

    def audits_for(self, developer_id: UUID) -> tuple[DeveloperAuditRecord, ...]:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT da.action,actor.name,da.details,da.created_at FROM developer_audits da JOIN users actor ON actor.id=da.actor_id WHERE da.target_developer_id=%s ORDER BY da.created_at DESC LIMIT 20",
                    (developer_id,),
                )
                return tuple(DeveloperAuditRecord(*row) for row in cursor.fetchall())

    @staticmethod
    def _replace_permissions(
        cursor: Any, developer_id: UUID, permissions: tuple[PermissionRecord, ...]
    ) -> None:
        cursor.execute("DELETE FROM user_permissions WHERE user_id=%s", (developer_id,))
        for permission in permissions:
            cursor.execute(
                "INSERT INTO user_permissions(user_id,module_id,permission_id) SELECT %s,m.id,p.id FROM modules m CROSS JOIN permissions p WHERE m.code=%s AND p.code=%s",
                (developer_id, permission.module, permission.action),
            )
            if cursor.rowcount != 1:
                raise ValueError(f"Invalid permission {permission.module}:{permission.action}")

    def create_developer(
        self,
        *,
        actor_id: UUID,
        first_name: str,
        last_name: str,
        email: str,
        phone: str,
        password_hash: str,
        status: str,
        permissions: tuple[PermissionRecord, ...],
    ) -> DeveloperRecord:
        try:
            with database_pool.connection(timeout=2) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT id FROM roles WHERE code='DEVELOPER'")
                    role = cursor.fetchone()
                    if not role:
                        raise RuntimeError("Developer role is not initialized.")
                    developer_id = uuid4()
                    name = f"{first_name} {last_name}".strip()
                    cursor.execute(
                        "INSERT INTO users(id,name,email,password_hash,status,role_id,first_name,last_name,phone_number,created_at,updated_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW(),NOW())",
                        (
                            developer_id,
                            name,
                            email,
                            password_hash,
                            status,
                            role[0],
                            first_name,
                            last_name,
                            phone,
                        ),
                    )
                    self._replace_permissions(cursor, developer_id, permissions)
                    cursor.execute(
                        "INSERT INTO developer_audits(id,actor_id,target_developer_id,action,details) VALUES(%s,%s,%s,'DEVELOPER_CREATED',%s)",
                        (
                            uuid4(),
                            actor_id,
                            developer_id,
                            "Developer account and permissions created",
                        ),
                    )
            developer = self.get_developer(developer_id)
            if developer is None:
                raise RuntimeError("Created Developer was not found.")
            return developer
        except UniqueViolation as error:
            raise ValueError("Email address is already registered.") from error

    def update_developer(
        self,
        *,
        actor_id: UUID,
        developer_id: UUID,
        first_name: str,
        last_name: str,
        phone: str,
        status: str,
        permissions: tuple[PermissionRecord, ...],
    ) -> DeveloperRecord | None:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                name = f"{first_name} {last_name}".strip()
                cursor.execute(
                    "UPDATE users u SET name=%s,first_name=%s,last_name=%s,phone_number=%s,status=%s,updated_at=NOW() FROM roles r WHERE u.role_id=r.id AND u.id=%s AND r.code='DEVELOPER'",
                    (name, first_name, last_name, phone, status, developer_id),
                )
                if cursor.rowcount != 1:
                    return None
                cursor.execute(
                    "SELECT m.code,p.code FROM user_permissions up JOIN modules m ON m.id=up.module_id JOIN permissions p ON p.id=up.permission_id WHERE up.user_id=%s",
                    (developer_id,),
                )
                previous_permissions = {(row[0], row[1]) for row in cursor.fetchall()}
                self._replace_permissions(cursor, developer_id, permissions)
                if status == "INACTIVE":
                    cursor.execute(
                        "UPDATE auth_sessions SET status='REVOKED',refresh_token_hash=CONCAT('revoked:',id),last_activity_at=NOW() WHERE user_id=%s AND status='ACTIVE'",
                        (developer_id,),
                    )
                cursor.execute(
                    "INSERT INTO developer_audits(id,actor_id,target_developer_id,action,details) VALUES(%s,%s,%s,'DEVELOPER_UPDATED',%s)",
                    (uuid4(), actor_id, developer_id, "Profile, status, or permissions updated"),
                )
                next_permissions = {(item.module, item.action) for item in permissions}
                if previous_permissions != next_permissions:
                    cursor.execute(
                        "INSERT INTO developer_audits(id,actor_id,target_developer_id,action,details) VALUES(%s,%s,%s,'DEVELOPER_PERMISSIONS_UPDATED',%s)",
                        (
                            uuid4(),
                            actor_id,
                            developer_id,
                            f"Permission set changed from {len(previous_permissions)} to {len(next_permissions)} grants",
                        ),
                    )
        return self.get_developer(developer_id)

    def update_status(
        self, *, actor_id: UUID, developer_id: UUID, status: str
    ) -> DeveloperRecord | None:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE users u SET status=%s,updated_at=NOW() FROM roles r WHERE u.role_id=r.id AND u.id=%s AND r.code='DEVELOPER'",
                    (status, developer_id),
                )
                if cursor.rowcount != 1:
                    return None
                if status == "INACTIVE":
                    cursor.execute(
                        "UPDATE auth_sessions SET status='REVOKED',refresh_token_hash=CONCAT('revoked:',id),last_activity_at=NOW() WHERE user_id=%s AND status='ACTIVE'",
                        (developer_id,),
                    )
                action = "DEVELOPER_ACTIVATED" if status == "ACTIVE" else "DEVELOPER_DEACTIVATED"
                cursor.execute(
                    "INSERT INTO developer_audits(id,actor_id,target_developer_id,action,details) VALUES(%s,%s,%s,%s,%s)",
                    (uuid4(), actor_id, developer_id, action, f"Status changed to {status}"),
                )
        return self.get_developer(developer_id)

    def foundation_is_ready(self) -> bool:
        try:
            with database_pool.connection(timeout=2) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT to_regclass('public.user_permissions') IS NOT NULL AND to_regclass('public.developer_audits') IS NOT NULL"
                    )
                    row = cursor.fetchone()
                    return bool(row and row[0])
        except Exception:
            return False
