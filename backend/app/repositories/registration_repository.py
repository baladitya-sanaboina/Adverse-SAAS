from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from psycopg.errors import UniqueViolation

from app.database.connectivity import database_pool
from app.repositories.service_pricing_repository import seed_default_services


@dataclass(frozen=True)
class ActorRecord:
    id: UUID
    role_code: str
    status: str
    company_id: UUID | None


@dataclass(frozen=True)
class CompanyRecord:
    id: UUID
    status: str
    subscription_plan: str


@dataclass(frozen=True)
class CompanyLookupRecord:
    id: UUID
    name: str
    code: str
    status: str
    subscription_plan: str


@dataclass(frozen=True)
class CreatedUserRecord:
    id: UUID
    name: str
    email: str
    status: str
    role: str
    company_id: UUID | None
    created_at: datetime


@dataclass(frozen=True)
class CreatedCompanyRecord:
    id: UUID
    name: str
    code: str
    subscription_plan: str
    status: str
    contact_email: str | None
    created_at: datetime


class RegistrationConflict(Exception):
    def __init__(self, constraint_name: str | None):
        self.constraint_name = constraint_name
        super().__init__(constraint_name or "registration conflict")


class RegistrationRepository:
    @staticmethod
    def _assign_initial_plan(cursor: Any, company_id: UUID, subscription_plan: str) -> None:
        cursor.execute(
            "INSERT INTO company_subscriptions(id,company_id,plan_id,status,activation_date,created_at,updated_at) "
            "SELECT %s,%s,p.id,'ACTIVE',NOW(),NOW(),NOW() FROM subscription_plans p "
            "WHERE UPPER(p.name)=UPPER(%s) OR p.code=UPPER(%s) ORDER BY CASE WHEN UPPER(p.name)=UPPER(%s) THEN 0 ELSE 1 END LIMIT 1 "
            "ON CONFLICT(company_id) DO NOTHING",
            (uuid4(), company_id, subscription_plan, subscription_plan, subscription_plan),
        )

    def find_actor(self, actor_id: UUID) -> ActorRecord | None:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT users.id, roles.code, users.status::text, users.company_id "
                    'FROM "users" JOIN "roles" ON roles.id = users.role_id '
                    "WHERE users.id = %s",
                    (actor_id,),
                )
                record = cursor.fetchone()
                return ActorRecord(*record) if record else None

    def find_company(self, company_id: UUID) -> CompanyRecord | None:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    'SELECT id, status::text, subscription_plan FROM "companies" WHERE id = %s',
                    (company_id,),
                )
                record = cursor.fetchone()
                return CompanyRecord(*record) if record else None

    def find_company_by_code(self, code: str) -> CompanyLookupRecord | None:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    'SELECT id, name, code, status::text, subscription_plan FROM "companies" '
                    'WHERE UPPER(code) = UPPER(%s)',
                    (code,),
                )
                record = cursor.fetchone()
                return CompanyLookupRecord(*record) if record else None

    def email_exists(self, email: str) -> bool:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    'SELECT EXISTS (SELECT 1 FROM "users" WHERE LOWER(email) = LOWER(%s))',
                    (email,),
                )
                record = cursor.fetchone()
                return bool(record and record[0])

    def list_users(
        self, *, role_code: str, company_id: UUID | None = None
    ) -> tuple[CreatedUserRecord, ...]:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT u.id, u.name, u.email, u.status::text, r.code, u.company_id, u.created_at "
                    'FROM "users" u JOIN "roles" r ON r.id = u.role_id '
                    "WHERE r.code = %s AND (%s::uuid IS NULL OR u.company_id = %s) "
                    "ORDER BY u.created_at DESC",
                    (role_code, company_id, company_id),
                )
                return tuple(CreatedUserRecord(*record) for record in cursor.fetchall())

    def list_companies(self, *, actor_id: UUID) -> tuple[CreatedCompanyRecord, ...]:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT c.id, c.name, c.code, c.subscription_plan, c.status::text, "
                    'c.contact_email, c.created_at FROM "companies" c '
                    'JOIN "registration_audits" a ON a.company_id = c.id '
                    "WHERE a.actor_id = %s AND a.action = 'COMPANY_CREATED' "
                    "ORDER BY c.created_at DESC",
                    (actor_id,),
                )
                return tuple(CreatedCompanyRecord(*record) for record in cursor.fetchall())

    def create_user(
        self,
        *,
        actor_id: UUID | None,
        name: str,
        email: str,
        password_hash: str,
        role_code: str,
        company_id: UUID | None,
    ) -> CreatedUserRecord:
        try:
            with database_pool.connection(timeout=2) as connection:
                with connection.cursor() as cursor:
                    cursor.execute('SELECT id FROM "roles" WHERE code = %s', (role_code,))
                    role_record = cursor.fetchone()
                    if role_record is None:
                        raise RuntimeError(f"Role {role_code} is not initialized.")
                    user_id = uuid4()
                    cursor.execute(
                        'INSERT INTO "users" '
                        "(id, name, email, password_hash, status, company_id, role_id, created_at, updated_at) "
                        "VALUES (%s, %s, %s, %s, 'PENDING_VERIFICATION', %s, %s, NOW(), NOW()) "
                        "RETURNING id, name, email, status::text, created_at",
                        (user_id, name, email, password_hash, company_id, role_record[0]),
                    )
                    user_record = cursor.fetchone()
                    if user_record is None:
                        raise RuntimeError("User creation did not return a record.")
                    audit_actor_id = actor_id or user_id
                    cursor.execute(
                        'INSERT INTO "registration_audits" '
                        "(id, action, actor_id, created_user_id, company_id, role_code, created_at) "
                        "VALUES (%s, 'USER_CREATED', %s, %s, %s, %s, NOW())",
                        (uuid4(), audit_actor_id, user_id, company_id, role_code),
                    )
                    if role_code in {"COMPANY_EMPLOYEE", "COMPANY_MANAGER"} and company_id is not None:
                        employee_code_prefix = "MGR" if role_code == "COMPANY_MANAGER" else "EMP"
                        cursor.execute(
                            "INSERT INTO employees("
                            "id,company_id,user_id,employee_code,department_id,branch_id,role_id,status,created_at,updated_at"
                            ") VALUES(%s,%s,%s,%s,NULL,NULL,%s,'PENDING',NOW(),NOW())",
                            (
                                uuid4(),
                                company_id,
                                user_id,
                                f"{employee_code_prefix}-{str(user_id).replace('-', '')[:8].upper()}",
                                role_record[0],
                            ),
                        )
                    if role_code == "COMPANY_CLIENT" and company_id is not None:
                        self._link_client_account_if_match(cursor, company_id, user_id, email)
                    return CreatedUserRecord(
                        id=user_record[0],
                        name=user_record[1],
                        email=user_record[2],
                        status=user_record[3],
                        role=role_code,
                        company_id=company_id,
                        created_at=user_record[4],
                    )
        except UniqueViolation as error:
            raise RegistrationConflict(error.diag.constraint_name) from error

    @staticmethod
    def _link_client_account_if_match(
        cursor: Any, company_id: UUID, user_id: UUID, email: str
    ) -> None:
        cursor.execute(
            "SELECT id FROM clients WHERE company_id=%s AND LOWER(email)=LOWER(%s) "
            "AND (user_id IS NULL OR user_id=%s) ORDER BY created_at ASC LIMIT 1 FOR UPDATE",
            (company_id, email, user_id),
        )
        client = cursor.fetchone()
        if client is None:
            return
        cursor.execute(
            "UPDATE clients SET user_id=%s,updated_at=NOW() WHERE id=%s",
            (user_id, client[0]),
        )

    def create_company(
        self,
        *,
        actor_id: UUID,
        name: str,
        code: str,
        subscription_plan: str,
        contact_email: str | None,
    ) -> CreatedCompanyRecord:
        try:
            with database_pool.connection(timeout=2) as connection:
                with connection.cursor() as cursor:
                    company_id = uuid4()
                    cursor.execute(
                        'INSERT INTO "companies" '
                        "(id, name, code, subscription_plan, status, contact_email, created_at, updated_at) "
                        "VALUES (%s, %s, %s, %s, 'ACTIVE', %s, NOW(), NOW()) "
                        "RETURNING id, name, code, subscription_plan, status::text, contact_email, created_at",
                        (company_id, name, code, subscription_plan, contact_email),
                    )
                    company_record = cursor.fetchone()
                    if company_record is None:
                        raise RuntimeError("Company creation did not return a record.")
                    self._assign_initial_plan(cursor, company_id, subscription_plan)
                    seed_default_services(cursor, company_id)
                    cursor.execute(
                        'INSERT INTO "registration_audits" '
                        "(id, action, actor_id, company_id, created_at) "
                        "VALUES (%s, 'COMPANY_CREATED', %s, %s, NOW())",
                        (uuid4(), actor_id, company_id),
                    )
                    return CreatedCompanyRecord(*company_record)
        except UniqueViolation as error:
            raise RegistrationConflict(error.diag.constraint_name) from error

    def create_company_with_admin(
        self,
        *,
        actor_id: UUID | None,
        company_name: str,
        company_code: str,
        subscription_plan: str,
        contact_email: str | None,
        admin_name: str,
        admin_email: str,
        admin_password_hash: str,
    ) -> tuple[CreatedCompanyRecord, CreatedUserRecord]:
        try:
            with database_pool.connection(timeout=2) as connection:
                with connection.cursor() as cursor:
                    cursor.execute('SELECT id FROM "roles" WHERE code = %s', ("COMPANY_ADMIN",))
                    role_record = cursor.fetchone()
                    if role_record is None:
                        raise RuntimeError("Role COMPANY_ADMIN is not initialized.")
                    company_id = uuid4()
                    cursor.execute(
                        'INSERT INTO "companies" '
                        "(id, name, code, subscription_plan, status, contact_email, created_at, updated_at) "
                        "VALUES (%s, %s, %s, %s, 'ACTIVE', %s, NOW(), NOW()) "
                        "RETURNING id, name, code, subscription_plan, status::text, contact_email, created_at",
                        (
                            company_id,
                            company_name,
                            company_code,
                            subscription_plan,
                            contact_email,
                        ),
                    )
                    company_record = cursor.fetchone()
                    if company_record is None:
                        raise RuntimeError("Company creation did not return a record.")
                    self._assign_initial_plan(cursor, company_id, subscription_plan)
                    seed_default_services(cursor, company_id)
                    user_id = uuid4()
                    cursor.execute(
                        'INSERT INTO "users" '
                        "(id, name, email, password_hash, status, company_id, role_id, created_at, updated_at) "
                        "VALUES (%s, %s, %s, %s, 'PENDING_VERIFICATION', %s, %s, NOW(), NOW()) "
                        "RETURNING id, name, email, status::text, created_at",
                        (
                            user_id,
                            admin_name,
                            admin_email,
                            admin_password_hash,
                            company_id,
                            role_record[0],
                        ),
                    )
                    user_record = cursor.fetchone()
                    if user_record is None:
                        raise RuntimeError("Company Admin creation did not return a record.")
                    audit_actor_id = actor_id or user_id
                    cursor.execute(
                        'INSERT INTO "registration_audits" '
                        "(id, action, actor_id, company_id, created_at) "
                        "VALUES (%s, 'COMPANY_CREATED', %s, %s, NOW())",
                        (uuid4(), audit_actor_id, company_id),
                    )
                    cursor.execute(
                        'INSERT INTO "registration_audits" '
                        "(id, action, actor_id, created_user_id, company_id, role_code, created_at) "
                        "VALUES (%s, 'USER_CREATED', %s, %s, %s, 'COMPANY_ADMIN', NOW())",
                        (uuid4(), audit_actor_id, user_id, company_id),
                    )
                    return (
                        CreatedCompanyRecord(*company_record),
                        CreatedUserRecord(
                            id=user_record[0],
                            name=user_record[1],
                            email=user_record[2],
                            status=user_record[3],
                            role="COMPANY_ADMIN",
                            company_id=company_id,
                            created_at=user_record[4],
                        ),
                    )
        except UniqueViolation as error:
            raise RegistrationConflict(error.diag.constraint_name) from error

    def foundation_is_ready(self) -> bool:
        try:
            with database_pool.connection(timeout=2) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT EXISTS (SELECT 1 FROM pg_tables "
                        "WHERE schemaname = 'public' AND tablename = 'registration_audits')"
                    )
                    table_record = cursor.fetchone()
                    return bool(table_record and table_record[0])
        except Exception:
            return False
