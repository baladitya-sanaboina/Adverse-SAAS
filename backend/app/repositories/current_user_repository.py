from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from app.database.connectivity import database_pool


@dataclass(frozen=True)
class CurrentUserRecord:
    id: UUID
    name: str
    email: str
    status: str
    created_at: datetime
    company_id: UUID | None
    company_name: str | None
    company_code: str | None
    subscription_plan: str | None
    company_status: str | None
    subscription_features: dict[str, bool]
    role_id: UUID
    role_name: str
    role_code: str
    profile_image_url: str | None = None


@dataclass(frozen=True)
class CurrentUserPermissionRecord:
    module: str
    module_name: str
    action: str
    action_name: str


class CurrentUserRepository:
    def load_profile(self, user_id: UUID) -> CurrentUserRecord | None:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT u.id, u.name, u.email, u.status::text, u.created_at, "
                    "c.id, c.name, c.code, c.subscription_plan, c.status::text, "
                    "COALESCE((SELECT jsonb_object_agg(spf.feature_code, spf.enabled) "
                    "FROM company_subscriptions cs JOIN subscription_plan_features spf "
                    "ON spf.plan_id = cs.plan_id WHERE cs.company_id = c.id "
                    "AND cs.status = 'ACTIVE'), '{}'::jsonb), "
                    'r.id, r.name, r.code, u.profile_image_url FROM "users" u '
                    'JOIN "roles" r ON r.id = u.role_id '
                    'LEFT JOIN "companies" c ON c.id = u.company_id WHERE u.id = %s',
                    (user_id,),
                )
                record = cursor.fetchone()
                if not record:
                    return None
                values: list[Any] = list(record)
                values[10] = dict(values[10])
                return CurrentUserRecord(*values)

    def load_permissions(
        self, role_id: UUID, user_id: UUID | None = None
    ) -> tuple[CurrentUserPermissionRecord, ...]:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                if user_id is not None:
                    cursor.execute(
                        'SELECT m.code, m.name, p.code, p.name FROM "user_permissions" up '
                        'JOIN "modules" m ON m.id = up.module_id '
                        'JOIN "permissions" p ON p.id = up.permission_id '
                        "WHERE up.user_id = %s ORDER BY m.code, p.code",
                        (user_id,),
                    )
                    user_permissions = tuple(
                        CurrentUserPermissionRecord(*row) for row in cursor.fetchall()
                    )
                    if user_permissions:
                        return user_permissions
                    cursor.execute('SELECT code FROM "roles" WHERE id = %s', (role_id,))
                    role_record = cursor.fetchone()
                    if role_record and role_record[0] == "DEVELOPER":
                        return ()
                cursor.execute(
                    'SELECT m.code, m.name, p.code, p.name FROM "role_permissions" rp '
                    'JOIN "modules" m ON m.id = rp.module_id '
                    'JOIN "permissions" p ON p.id = rp.permission_id '
                    "WHERE rp.role_id = %s ORDER BY m.code, p.code",
                    (role_id,),
                )
                return tuple(CurrentUserPermissionRecord(*row) for row in cursor.fetchall())

    def foundation_is_ready(self) -> bool:
        try:
            with database_pool.connection(timeout=2) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT to_regclass('public.users') IS NOT NULL "
                        "AND to_regclass('public.role_permissions') IS NOT NULL"
                    )
                    record = cursor.fetchone()
                    return bool(record and record[0])
        except Exception:
            return False
