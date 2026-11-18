import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast
from uuid import UUID, uuid4

from psycopg import Cursor
from psycopg.errors import UniqueViolation

from app.core.constants import RoleCode
from app.database.connectivity import database_pool


@dataclass(frozen=True)
class InvitationRecord:
    id: UUID
    email: str
    notification_email: str
    company_name: str
    invited_by_name: str
    role_code: str
    status: str
    expires_at: datetime
    accepted_at: datetime | None
    created_at: datetime


class InvitationConflict(Exception):
    pass


class InvitationRepository:
    _select = (
        "SELECT i.id,i.email,COALESCE(i.notification_email,i.email),c.name,u.name,i.role_code,"
        "CASE WHEN i.status='PENDING' AND i.expires_at<=NOW() THEN 'EXPIRED' ELSE i.status::text END,"
        "i.expires_at,i.accepted_at,i.created_at FROM company_invitations i "
        "JOIN companies c ON c.id=i.company_id JOIN users u ON u.id=i.invited_by "
    )

    @staticmethod
    def _expire() -> None:
        with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
            cursor.execute(
                "UPDATE company_invitations SET status='EXPIRED',updated_at=NOW() "
                "WHERE status='PENDING' AND expires_at<=NOW()"
            )

    @staticmethod
    def _role_id(cursor: Cursor[Any], role_code: str) -> UUID:
        cursor.execute('SELECT id FROM "roles" WHERE code=%s', (role_code,))
        role = cursor.fetchone()
        if not role:
            raise RuntimeError(f"Role {role_code} is unavailable.")
        return cast(UUID, role[0])

    @staticmethod
    def _link_client_account(
        cursor: Cursor[Any],
        company_id: UUID,
        user_id: UUID,
        *,
        client_id: UUID | None = None,
        email: str | None = None,
    ) -> None:
        if client_id is not None:
            cursor.execute(
                "SELECT id FROM clients WHERE company_id=%s AND id=%s "
                "AND (user_id IS NULL OR user_id=%s) LIMIT 1 FOR UPDATE",
                (company_id, client_id, user_id),
            )
            client = cursor.fetchone()
            if client is None:
                raise InvitationConflict("CLIENT_NOT_FOUND")
            cursor.execute(
                "UPDATE clients SET user_id=%s,updated_at=NOW() WHERE id=%s",
                (user_id, client[0]),
            )
            return
        if email is None:
            return
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

    @staticmethod
    def _ensure_employee_profile(
        cursor: Cursor[Any],
        company_id: UUID,
        user_id: UUID,
        role_id: UUID,
        status: str,
        role_code: str,
    ) -> None:
        employee_code_prefix = "MGR" if role_code == RoleCode.COMPANY_MANAGER else "EMP"
        cursor.execute(
            "SELECT id FROM employees WHERE company_id=%s AND user_id=%s LIMIT 1",
            (company_id, user_id),
        )
        row = cursor.fetchone()
        if row:
            cursor.execute(
                "UPDATE employees SET status=%s,role_id=%s,updated_at=NOW() WHERE id=%s",
                (status, role_id, row[0]),
            )
            return
        cursor.execute(
            "INSERT INTO employees("
            "id,company_id,user_id,employee_code,department_id,branch_id,role_id,status,created_at,updated_at"
            ") VALUES(%s,%s,%s,%s,NULL,NULL,%s,%s,NOW(),NOW())",
            (
                uuid4(),
                company_id,
                user_id,
                f"{employee_code_prefix}-{str(user_id).replace('-', '')[:8].upper()}",
                role_id,
                status,
            ),
        )

    def list(self, company_id: UUID) -> tuple[InvitationRecord, ...]:
        self._expire()
        with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
            cursor.execute(
                self._select + "WHERE i.company_id=%s ORDER BY i.created_at DESC", (company_id,)
            )
            return tuple(InvitationRecord(*row) for row in cursor.fetchall())

    def get(self, company_id: UUID, invitation_id: UUID) -> InvitationRecord | None:
        self._expire()
        with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
            cursor.execute(
                self._select + "WHERE i.company_id=%s AND i.id=%s", (company_id, invitation_id)
            )
            row = cursor.fetchone()
            return InvitationRecord(*row) if row else None

    def create(
        self,
        company_id: UUID,
        actor_id: UUID,
        email: str,
        notification_email: str | None,
        token_hash: str,
        expires_at: datetime,
        role_code: str,
        invited_name: str | None = None,
        phone_number: str | None = None,
        provisioned_password_hash: str | None = None,
        client_id: UUID | None = None,
    ) -> InvitationRecord:
        self._expire()
        notification_email = notification_email or email
        try:
            with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
                cursor.execute(
                    'SELECT u.id,u.status::text,r.code,u.company_id FROM "users" u '
                    'JOIN "roles" r ON r.id=u.role_id WHERE LOWER(u.email)=LOWER(%s) '
                    "ORDER BY u.created_at ASC LIMIT 1",
                    (email,),
                )
                existing = cursor.fetchone()
                user_id: UUID | None = None
                role_id: UUID | None = None
                if existing is not None:
                    existing_user_id, existing_status, existing_role_code, existing_company_id = (
                        existing
                    )
                    reusable = (
                        existing_status == "PENDING_VERIFICATION"
                        and existing_role_code == role_code
                        and existing_company_id == company_id
                    )
                    if not reusable:
                        raise InvitationConflict("USER_EXISTS")
                    user_id = existing_user_id
                    role_id = self._role_id(cursor, role_code)
                    if invited_name or phone_number:
                        cursor.execute(
                            'UPDATE "users" SET name=COALESCE(%s,name),phone_number=COALESCE(%s,phone_number),updated_at=NOW() '
                            "WHERE id=%s",
                            (invited_name, phone_number, user_id),
                        )
                    if role_code in {RoleCode.COMPANY_EMPLOYEE, RoleCode.COMPANY_MANAGER}:
                        self._ensure_employee_profile(
                            cursor, company_id, user_id, role_id, "PENDING", role_code
                        )
                    elif role_code == RoleCode.COMPANY_CLIENT:
                        self._link_client_account(
                            cursor,
                            company_id,
                            user_id,
                            client_id=client_id,
                            email=email,
                        )
                elif invited_name:
                    if provisioned_password_hash is None:
                        raise RuntimeError(
                            "Provisioned password hash is required when creating a pending account."
                        )
                    role_id = self._role_id(cursor, role_code)
                    user_id = uuid4()
                    cursor.execute(
                        'INSERT INTO "users" '
                        "(id, name, email, password_hash, status, company_id, role_id, phone_number, created_at, updated_at) "
                        "VALUES (%s, %s, LOWER(%s), %s, 'PENDING_VERIFICATION', %s, %s, %s, NOW(), NOW())",
                        (
                            user_id,
                            invited_name,
                            email,
                            provisioned_password_hash,
                            company_id,
                            role_id,
                            phone_number,
                        ),
                    )
                    cursor.execute(
                        'INSERT INTO "registration_audits" '
                        "(id, action, actor_id, created_user_id, company_id, role_code, created_at) "
                        "VALUES (%s, 'USER_CREATED', %s, %s, %s, %s, NOW())",
                        (uuid4(), actor_id, user_id, company_id, role_code),
                    )
                    if role_code in {RoleCode.COMPANY_EMPLOYEE, RoleCode.COMPANY_MANAGER}:
                        self._ensure_employee_profile(
                            cursor, company_id, user_id, role_id, "PENDING", role_code
                        )
                    elif role_code == RoleCode.COMPANY_CLIENT:
                        self._link_client_account(
                            cursor,
                            company_id,
                            user_id,
                            client_id=client_id,
                            email=email,
                        )
                invitation_id = uuid4()
                cursor.execute(
                    "INSERT INTO company_invitations("
                    "id,company_id,email,notification_email,invited_by,token_hash,expires_at,role_code,user_id,client_id,status,created_at,updated_at"
                    ") VALUES(%s,%s,LOWER(%s),LOWER(%s),%s,%s,%s,%s,%s,%s,'PENDING',NOW(),NOW())",
                    (
                        invitation_id,
                        company_id,
                        email,
                        notification_email,
                        actor_id,
                        token_hash,
                        expires_at,
                        role_code,
                        user_id,
                        client_id,
                    ),
                )
                details: dict[str, object] = {
                    "email": email,
                    "notification_email": notification_email,
                    "role": role_code,
                }
                if client_id is not None:
                    details["client_id"] = str(client_id)
                if user_id is not None:
                    details["provisioned_user_id"] = str(user_id)
                self._audit(
                    cursor, invitation_id, company_id, actor_id, "USER_INVITATION_CREATED", details
                )
            record = self.get(company_id, invitation_id)
            if record is None:
                raise RuntimeError("Invitation insert returned no record.")
            return record
        except UniqueViolation as error:
            raise InvitationConflict("INVITATION_EXISTS") from error

    def find_by_hash(
        self, token_hash: str
    ) -> tuple[InvitationRecord, UUID, UUID, UUID | None] | None:
        self._expire()
        with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
            cursor.execute(self._select + "WHERE i.token_hash=%s", (token_hash,))
            row = cursor.fetchone()
            if not row:
                return None
            cursor.execute(
                "SELECT company_id,invited_by,user_id FROM company_invitations WHERE token_hash=%s",
                (token_hash,),
            )
            scope = cursor.fetchone()
            if not scope:
                return None
            return InvitationRecord(*row), scope[0], scope[1], scope[2]

    def audit_validation_failure(
        self,
        found: tuple[InvitationRecord, UUID, UUID, UUID | None] | None,
        reason: str,
    ) -> None:
        record = found[0] if found else None
        company_id = found[1] if found else None
        with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
            self._audit(
                cursor,
                record.id if record else None,
                company_id,
                None,
                "USER_INVITATION_VALIDATION_FAILED",
                {"reason": reason},
            )

    def resend(
        self,
        company_id: UUID,
        invitation_id: UUID,
        actor_id: UUID,
        token_hash: str,
        expires_at: datetime,
    ) -> InvitationRecord | None:
        with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
            cursor.execute(
                "UPDATE company_invitations SET token_hash=%s,expires_at=%s,status='PENDING',accepted_at=NULL,updated_at=NOW() "
                "WHERE id=%s AND company_id=%s AND status<>'ACCEPTED' AND status<>'REVOKED' RETURNING id",
                (token_hash, expires_at, invitation_id, company_id),
            )
            if not cursor.fetchone():
                return None
            self._audit(cursor, invitation_id, company_id, actor_id, "USER_INVITATION_RESENT", {})
        return self.get(company_id, invitation_id)

    def revoke(
        self, company_id: UUID, invitation_id: UUID, actor_id: UUID
    ) -> InvitationRecord | None:
        with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
            cursor.execute(
                "UPDATE company_invitations SET status='REVOKED',updated_at=NOW() "
                "WHERE id=%s AND company_id=%s AND status IN ('PENDING','EXPIRED') RETURNING id",
                (invitation_id, company_id),
            )
            if not cursor.fetchone():
                return None
            self._audit(cursor, invitation_id, company_id, actor_id, "USER_INVITATION_REVOKED", {})
        return self.get(company_id, invitation_id)

    def accept(
        self, token_hash: str, name: str, password_hash: str
    ) -> tuple[str, str, str, str] | None:
        try:
            with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id,company_id,email,COALESCE(notification_email,email),role_code,user_id,status::text,expires_at,client_id "
                    "FROM company_invitations "
                    "WHERE token_hash=%s FOR UPDATE",
                    (token_hash,),
                )
                row = cursor.fetchone()
                if not row:
                    return None
                (
                    invitation_id,
                    company_id,
                    email,
                    notification_email,
                    role_code,
                    provisioned_user_id,
                    status,
                    expires_at,
                    client_id,
                ) = row
                if status != "PENDING" or expires_at <= datetime.now(expires_at.tzinfo):
                    return None
                role_id = self._role_id(cursor, role_code)
                if provisioned_user_id is not None:
                    user_id = provisioned_user_id
                    cursor.execute(
                        "UPDATE \"users\" SET name=%s,password_hash=%s,status='ACTIVE',updated_at=NOW() "
                        "WHERE id=%s RETURNING id",
                        (name, password_hash, user_id),
                    )
                    if cursor.fetchone() is None:
                        return None
                    if role_code in {RoleCode.COMPANY_EMPLOYEE, RoleCode.COMPANY_MANAGER}:
                        self._ensure_employee_profile(
                            cursor, company_id, user_id, role_id, "ACTIVE", role_code
                        )
                    elif role_code == RoleCode.COMPANY_CLIENT:
                        self._link_client_account(
                            cursor,
                            company_id,
                            user_id,
                            client_id=client_id,
                            email=email,
                        )
                else:
                    user_id = uuid4()
                    cursor.execute(
                        'INSERT INTO "users" '
                        "(id,name,email,password_hash,status,company_id,role_id,created_at,updated_at) "
                        "VALUES(%s,%s,LOWER(%s),%s,'ACTIVE',%s,%s,NOW(),NOW())",
                        (user_id, name, email, password_hash, company_id, role_id),
                    )
                    if role_code in {RoleCode.COMPANY_EMPLOYEE, RoleCode.COMPANY_MANAGER}:
                        self._ensure_employee_profile(
                            cursor, company_id, user_id, role_id, "ACTIVE", role_code
                        )
                    elif role_code == RoleCode.COMPANY_CLIENT:
                        self._link_client_account(
                            cursor,
                            company_id,
                            user_id,
                            client_id=client_id,
                            email=email,
                        )
                cursor.execute(
                    "UPDATE company_invitations SET status='ACCEPTED',accepted_at=NOW(),updated_at=NOW() WHERE id=%s",
                    (invitation_id,),
                )
                self._audit(
                    cursor,
                    invitation_id,
                    company_id,
                    user_id,
                    "USER_INVITATION_ACCEPTED",
                    {"email": email, "role": role_code},
                )
                self._audit(
                    cursor,
                    invitation_id,
                    company_id,
                    user_id,
                    "USER_ACCOUNT_CREATED",
                    {"email": email, "role": role_code},
                )
                self._audit(
                    cursor,
                    invitation_id,
                    company_id,
                    user_id,
                    "USER_ACCOUNT_ACTIVATED",
                    {"email": email, "status": "ACTIVE", "role": role_code},
                )
                cursor.execute("SELECT name FROM companies WHERE id=%s", (company_id,))
                company = cursor.fetchone()
                if not company:
                    raise RuntimeError("Invitation company is unavailable.")
                company_name = company[0]
                return email, notification_email, company_name, role_code
        except UniqueViolation as error:
            raise InvitationConflict("USER_EXISTS") from error

    @staticmethod
    def _audit(
        cursor: Cursor[Any],
        invitation_id: UUID | None,
        company_id: UUID | None,
        actor_id: UUID | None,
        action: str,
        details: dict[str, object],
    ) -> None:
        cursor.execute(
            "INSERT INTO invitation_audits(id,invitation_id,company_id,actor_id,action,details,created_at) "
            "VALUES(%s,%s,%s,%s,%s,%s::jsonb,NOW())",
            (uuid4(), invitation_id, company_id, actor_id, action, json.dumps(details)),
        )

    def is_ready(self) -> bool:
        try:
            with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
                cursor.execute("SELECT to_regclass('public.company_invitations') IS NOT NULL")
                row = cursor.fetchone()
                return bool(row and row[0])
        except Exception:
            return False
