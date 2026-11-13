from dataclasses import dataclass

from app.database.connectivity import database_pool


@dataclass(frozen=True)
class PermissionGrant:
    module: str
    action: str


@dataclass(frozen=True)
class RbacHealth:
    initialized: bool
    roles: tuple[str, ...] = ()
    modules: tuple[str, ...] = ()
    permissions: tuple[str, ...] = ()
    mapping_count: int = 0


def load_user_role(user_id: str) -> str | None:
    with database_pool.connection(timeout=2) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT roles.code FROM "users" '
                'JOIN "roles" ON roles.id = users.role_id WHERE users.id = %s',
                (user_id,),
            )
            record = cursor.fetchone()
            return record[0] if record else None


def load_role_permissions(role_code: str) -> tuple[PermissionGrant, ...]:
    with database_pool.connection(timeout=2) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT modules.code, permissions.code FROM "role_permissions" '
                'JOIN "roles" ON roles.id = role_permissions.role_id '
                'JOIN "modules" ON modules.id = role_permissions.module_id '
                'JOIN "permissions" ON permissions.id = role_permissions.permission_id '
                "WHERE roles.code = %s ORDER BY modules.code, permissions.code",
                (role_code,),
            )
            return tuple(PermissionGrant(module=row[0], action=row[1]) for row in cursor.fetchall())


def validate_module_access(role_code: str, module_code: str) -> bool:
    return any(grant.module == module_code for grant in load_role_permissions(role_code))


def validate_action_access(role_code: str, module_code: str, action_code: str) -> bool:
    expected = PermissionGrant(module=module_code, action=action_code)
    return expected in load_role_permissions(role_code)


def validate_user_action_access(
    user_id: str, role_code: str, module_code: str, action_code: str
) -> bool:
    """Resolve effective access at request time so permission changes apply immediately."""
    if role_code == "PLATFORM_OWNER":
        return True
    with database_pool.connection(timeout=2) as connection:
        with connection.cursor() as cursor:
            if role_code == "DEVELOPER":
                cursor.execute(
                    'SELECT EXISTS(SELECT 1 FROM "user_permissions" up '
                    'JOIN "modules" m ON m.id=up.module_id '
                    'JOIN "permissions" p ON p.id=up.permission_id '
                    "WHERE up.user_id=%s AND m.code=%s AND p.code=%s)",
                    (user_id, module_code, action_code),
                )
            else:
                cursor.execute(
                    'SELECT EXISTS(SELECT 1 FROM "role_permissions" rp '
                    'JOIN "roles" r ON r.id=rp.role_id '
                    'JOIN "modules" m ON m.id=rp.module_id '
                    'JOIN "permissions" p ON p.id=rp.permission_id '
                    "WHERE r.code=%s AND m.code=%s AND p.code=%s)",
                    (role_code, module_code, action_code),
                )
            record = cursor.fetchone()
            return bool(record and record[0])


def get_rbac_health() -> RbacHealth:
    try:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute('SELECT name FROM "roles" ORDER BY name')
                roles = tuple(row[0] for row in cursor.fetchall())
                cursor.execute('SELECT name FROM "modules" ORDER BY name')
                modules = tuple(row[0] for row in cursor.fetchall())
                cursor.execute('SELECT name FROM "permissions" ORDER BY name')
                permissions = tuple(row[0] for row in cursor.fetchall())
                cursor.execute('SELECT COUNT(*) FROM "role_permissions"')
                mapping_record = cursor.fetchone()
                mapping_count = int(mapping_record[0]) if mapping_record else 0

        return RbacHealth(
            initialized=(
                len(roles) >= 5
                and len(modules) >= 18
                and len(permissions) >= 9
                and mapping_count >= 52
            ),
            roles=roles,
            modules=modules,
            permissions=permissions,
            mapping_count=mapping_count,
        )
    except Exception:
        return RbacHealth(initialized=False)
