import json
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from psycopg import Cursor
from psycopg.errors import UniqueViolation

from app.database.connectivity import database_pool


@dataclass(frozen=True)
class InvitationRecord:
    id: UUID
    email: str
    company_name: str
    invited_by_name: str
    status: str
    expires_at: datetime
    accepted_at: datetime | None
    created_at: datetime


class InvitationConflict(Exception):
    pass


class InvitationRepository:
    _select = (
        "SELECT i.id,i.email,c.name,u.name,"
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
        self, company_id: UUID, actor_id: UUID, email: str, token_hash: str, expires_at: datetime
    ) -> InvitationRecord:
        self._expire()
        try:
            with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
                cursor.execute(
                    "SELECT EXISTS(SELECT 1 FROM users WHERE LOWER(email)=LOWER(%s))", (email,)
                )
                existing_user = cursor.fetchone()
                if existing_user and existing_user[0]:
                    raise InvitationConflict("USER_EXISTS")
                invitation_id = uuid4()
                cursor.execute(
                    "INSERT INTO company_invitations(id,company_id,email,invited_by,token_hash,expires_at,status,created_at,updated_at) "
                    "VALUES(%s,%s,LOWER(%s),%s,%s,%s,'PENDING',NOW(),NOW())",
                    (invitation_id, company_id, email, actor_id, token_hash, expires_at),
                )
                self._audit(
                    cursor,
                    invitation_id,
                    company_id,
                    actor_id,
                    "USER_INVITATION_CREATED",
                    {"email": email},
                )
            record = self.get(company_id, invitation_id)
            if record is None:
                raise RuntimeError("Invitation insert returned no record.")
            return record
        except UniqueViolation as error:
            raise InvitationConflict("INVITATION_EXISTS") from error

    def find_by_hash(self, token_hash: str) -> tuple[InvitationRecord, UUID, UUID] | None:
        self._expire()
        with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
            cursor.execute(self._select + "WHERE i.token_hash=%s", (token_hash,))
            row = cursor.fetchone()
            if not row:
                return None
            cursor.execute(
                "SELECT company_id,invited_by FROM company_invitations WHERE token_hash=%s",
                (token_hash,),
            )
            scope = cursor.fetchone()
            if not scope:
                return None
            return InvitationRecord(*row), scope[0], scope[1]

    def audit_validation_failure(
        self,
        found: tuple[InvitationRecord, UUID, UUID] | None,
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

    def accept(self, token_hash: str, name: str, password_hash: str) -> tuple[str, str] | None:
        try:
            with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id,company_id,email,status::text,expires_at FROM company_invitations "
                    "WHERE token_hash=%s FOR UPDATE",
                    (token_hash,),
                )
                row = cursor.fetchone()
                if not row:
                    return None
                invitation_id, company_id, email, status, expires_at = row
                if status != "PENDING" or expires_at <= datetime.now(expires_at.tzinfo):
                    return None
                cursor.execute("SELECT id FROM roles WHERE code='COMPANY_EMPLOYEE'")
                role = cursor.fetchone()
                if not role:
                    raise RuntimeError("Company Employee role is unavailable.")
                user_id = uuid4()
                cursor.execute(
                    "INSERT INTO users(id,name,email,password_hash,status,company_id,role_id,created_at,updated_at) "
                    "VALUES(%s,%s,LOWER(%s),%s,'ACTIVE',%s,%s,NOW(),NOW())",
                    (user_id, name, email, password_hash, company_id, role[0]),
                )
                cursor.execute(
                    "INSERT INTO employees("
                    "id,company_id,user_id,employee_code,department_id,branch_id,role_id,status,created_at,updated_at"
                    ") VALUES(%s,%s,%s,%s,NULL,NULL,%s,'ACTIVE',NOW(),NOW())",
                    (
                        uuid4(),
                        company_id,
                        user_id,
                        f"EMP-{str(user_id).replace('-', '')[:8].upper()}",
                        role[0],
                    ),
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
                    {"email": email},
                )
                self._audit(
                    cursor,
                    invitation_id,
                    company_id,
                    user_id,
                    "USER_ACCOUNT_CREATED",
                    {"email": email, "role": "COMPANY_EMPLOYEE"},
                )
                self._audit(
                    cursor,
                    invitation_id,
                    company_id,
                    user_id,
                    "USER_ACCOUNT_ACTIVATED",
                    {"email": email, "status": "ACTIVE"},
                )
                cursor.execute("SELECT name FROM companies WHERE id=%s", (company_id,))
                company = cursor.fetchone()
                if not company:
                    raise RuntimeError("Invitation company is unavailable.")
                company_name = company[0]
                return email, company_name
        except UniqueViolation as error:
            raise InvitationConflict("USER_EXISTS") from error

    @staticmethod
    def _audit(
        cursor: Cursor[object],
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
