from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from psycopg.errors import ForeignKeyViolation, RestrictViolation, UniqueViolation

from app.database.connectivity import database_pool
from app.schemas.client import ClientListFilters


@dataclass(frozen=True)
class ClientRecord:
    id: UUID
    company_id: UUID
    name: str
    code: str
    email: str | None
    phone: str | None
    website: str | None
    address: str
    city: str
    state: str
    country: str
    status: str
    created_at: datetime
    updated_at: datetime
    primary_contact_name: str | None = None
    primary_contact_email: str | None = None
    primary_contact_phone: str | None = None
    primary_contact_designation: str | None = None
    account_user_id: UUID | None = None
    account_name: str | None = None
    account_email: str | None = None
    account_status: str | None = None


@dataclass(frozen=True)
class ClientContactRecord:
    id: UUID
    client_id: UUID
    first_name: str
    last_name: str
    email: str | None
    phone: str | None
    designation: str
    is_primary: bool
    status: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class ClientNoteRecord:
    id: UUID
    client_id: UUID
    created_by_id: UUID
    created_by_name: str
    content: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class ClientFeedbackRecord:
    id: UUID
    client_id: UUID
    created_by_id: UUID
    created_by_name: str
    content: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class ClientActivityRecord:
    id: UUID
    client_id: UUID
    actor_id: UUID
    actor_name: str
    type: str
    description: str
    created_at: datetime


class ClientConflict(Exception):
    def __init__(self, field: str):
        self.field = field


class ClientReferenceError(Exception):
    pass


class ClientDeletionError(Exception):
    def __init__(self, reason: str):
        self.reason = reason


class ClientRepository:
    _client_fields = (
        "clients.id,clients.company_id,clients.name,clients.code,clients.email,clients.phone,"
        "clients.website,clients.address,clients.city,clients.state,clients.country,"
        "clients.status::text,clients.created_at,clients.updated_at"
    )
    _contact_fields = (
        "id,client_id,first_name,last_name,email,phone,designation,is_primary,"
        "status::text,created_at,updated_at"
    )
    _note_fields = (
        "note.id,note.client_id,note.created_by_id,creator.name,note.content,"
        "note.created_at,note.updated_at"
    )
    _feedback_fields = (
        "feedback.id,feedback.client_id,feedback.created_by_id,creator.name,"
        "feedback.content,feedback.created_at,feedback.updated_at"
    )
    _activity_fields = (
        "activity.id,activity.client_id,activity.actor_id,actor.name,activity.type,"
        "activity.description,activity.created_at"
    )
    _client_columns = {
        "name",
        "code",
        "email",
        "phone",
        "website",
        "address",
        "city",
        "state",
        "country",
        "status",
    }
    _contact_columns = {
        "first_name",
        "last_name",
        "email",
        "phone",
        "designation",
        "is_primary",
        "status",
    }

    def list(
        self, company_id: UUID, filters: ClientListFilters
    ) -> tuple[tuple[ClientRecord, ...], int]:
        clauses = ["clients.company_id=%s"]
        values: list[object] = [company_id]
        if filters.search:
            clauses.append(
                "(clients.name ILIKE %s OR clients.code ILIKE %s OR clients.email ILIKE %s)"
            )
            pattern = f"%{filters.search}%"
            values.extend((pattern, pattern, pattern))
        if filters.status is not None:
            clauses.append("clients.status=%s")
            values.append(filters.status)
        where = " AND ".join(clauses)
        with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
            cursor.execute(f"SELECT COUNT(*) FROM clients WHERE {where}", values)
            count = cursor.fetchone()
            total = int(count[0]) if count else 0
            cursor.execute(
                f"SELECT {self._client_fields},"
                "(SELECT CONCAT_WS(' ',contact.first_name,NULLIF(contact.last_name,'')) "
                "FROM client_contacts contact WHERE contact.client_id=clients.id "
                "AND contact.is_primary=true ORDER BY contact.updated_at DESC LIMIT 1),"
                "(SELECT contact.email FROM client_contacts contact "
                "WHERE contact.client_id=clients.id AND contact.is_primary=true "
                "ORDER BY contact.updated_at DESC LIMIT 1),"
                "(SELECT contact.phone FROM client_contacts contact "
                "WHERE contact.client_id=clients.id AND contact.is_primary=true "
                "ORDER BY contact.updated_at DESC LIMIT 1),"
                "(SELECT contact.designation FROM client_contacts contact "
                "WHERE contact.client_id=clients.id AND contact.is_primary=true "
                "ORDER BY contact.updated_at DESC LIMIT 1),"
                "clients.user_id,account_user.name,account_user.email,account_user.status::text "
                "FROM clients LEFT JOIN users account_user ON account_user.id=clients.user_id "
                f"WHERE {where} "
                "ORDER BY clients.name,clients.code LIMIT %s OFFSET %s",
                (*values, filters.page_size, (filters.page - 1) * filters.page_size),
            )
            return tuple(ClientRecord(*row) for row in cursor.fetchall()), total

    def get(self, company_id: UUID, client_id: UUID) -> ClientRecord | None:
        with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
            return self._get_client(cursor, company_id, client_id)

    def get_for_user(self, company_id: UUID, user_id: UUID) -> ClientRecord | None:
        with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM clients WHERE company_id=%s AND user_id=%s LIMIT 1",
                (company_id, user_id),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return self._get_client(cursor, company_id, row[0])

    def create(self, company_id: UUID, values: dict[str, object]) -> ClientRecord:
        normalized = self._allowed(values, self._client_columns)
        email = self._normalize_email(normalized.get("email"))
        normalized["email"] = email
        try:
            with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
                self._ensure_unique_email(cursor, company_id, email)
                if not normalized.get("code"):
                    normalized["code"] = self._next_code(cursor, company_id)
                client_id = uuid4()
                columns = ["id", "company_id", *normalized]
                params = [client_id, company_id, *normalized.values()]
                placeholders = ",".join(["%s"] * len(columns))
                cursor.execute(
                    f"INSERT INTO clients({','.join(columns)}) VALUES({placeholders}) "
                    "RETURNING id",
                    params,
                )
                row = cursor.fetchone()
                if row is None:
                    raise RuntimeError("Client insert returned no record.")
                record = self._get_client(cursor, company_id, client_id)
                if record is None:
                    raise RuntimeError("Client insert returned no record.")
                return record
        except UniqueViolation as error:
            raise ClientConflict(self._conflict_field(error)) from error

    @staticmethod
    def _next_code(cursor: Any, company_id: UUID) -> str:
        """The next automatic client code in this company: CLT-0001, CLT-0002, ... A lock per
        company keeps two clients added at the same moment from getting the same code."""
        cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"client-code:{company_id}",))
        cursor.execute(
            "SELECT COALESCE(MAX(CAST(SUBSTRING(code FROM '^CLT-([0-9]+)$') AS INTEGER)), 0) "
            "FROM clients WHERE company_id = %s AND code ~ '^CLT-[0-9]+$'",
            (company_id,),
        )
        row = cursor.fetchone()
        number = int(row[0] if row else 0) + 1
        while True:
            code = f"CLT-{number:04d}"
            cursor.execute(
                "SELECT 1 FROM clients WHERE company_id = %s AND UPPER(code) = %s",
                (company_id, code),
            )
            if cursor.fetchone() is None:
                return code
            number += 1

    def update(
        self,
        company_id: UUID,
        client_id: UUID,
        actor_id: UUID,
        values: dict[str, object],
    ) -> ClientRecord | None:
        normalized = self._allowed(values, self._client_columns)
        if "email" in normalized:
            email = self._normalize_email(normalized.get("email"))
            normalized["email"] = email
        if not normalized:
            return self.get(company_id, client_id)
        setters = ",".join(f"{column}=%s" for column in normalized)
        try:
            with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
                if "email" in normalized:
                    self._ensure_unique_email(
                        cursor,
                        company_id,
                        normalized.get("email"),
                        exclude_client_id=client_id,
                    )
                cursor.execute(
                    f"UPDATE clients SET {setters},updated_at=NOW() "
                    "WHERE id=%s AND company_id=%s RETURNING id",
                    (*normalized.values(), client_id, company_id),
                )
                row = cursor.fetchone()
                if row:
                    self._activity(
                        cursor,
                        company_id,
                        client_id,
                        actor_id,
                        "CLIENT_UPDATED",
                        "Client details were updated.",
                    )
                    return self._get_client(cursor, company_id, client_id)
                return None
        except UniqueViolation as error:
            raise ClientConflict(self._conflict_field(error)) from error

    def delete_pending(self, company_id: UUID, client_id: UUID) -> tuple[str, str | None] | None:
        try:
            with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
                cursor.execute(
                    "SELECT clients.user_id,clients.name,clients.email,account_user.status::text "
                    "FROM clients LEFT JOIN users account_user ON account_user.id=clients.user_id "
                    "WHERE clients.company_id=%s AND clients.id=%s FOR UPDATE OF clients",
                    (company_id, client_id),
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                user_id, client_name, client_email, account_status = row
                if user_id is not None and account_status != "PENDING_VERIFICATION":
                    raise ClientDeletionError("ACTIVE_ACCOUNT")
                cursor.execute(
                    "DELETE FROM company_invitations WHERE company_id=%s AND (client_id=%s OR user_id=%s)",
                    (company_id, client_id, user_id),
                )
                cursor.execute(
                    "DELETE FROM clients WHERE id=%s AND company_id=%s RETURNING id",
                    (client_id, company_id),
                )
                if cursor.fetchone() is None:
                    return None
                if user_id is not None:
                    cursor.execute(
                        "UPDATE registration_audits SET created_user_id=NULL WHERE created_user_id=%s",
                        (user_id,),
                    )
                    cursor.execute(
                        'DELETE FROM "users" WHERE id=%s AND company_id=%s AND status=%s RETURNING id',
                        (user_id, company_id, "PENDING_VERIFICATION"),
                    )
                    if cursor.fetchone() is None:
                        raise ClientDeletionError("ACTIVE_ACCOUNT")
                return client_name, client_email
        except (ForeignKeyViolation, RestrictViolation) as error:
            raise ClientDeletionError("IN_USE") from error

    def list_contacts(self, company_id: UUID, client_id: UUID) -> tuple[ClientContactRecord, ...]:
        with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
            self._lock_client(cursor, company_id, client_id, lock=False)
            cursor.execute(
                f"SELECT {self._contact_fields} FROM client_contacts WHERE client_id=%s "
                "ORDER BY is_primary DESC,first_name,last_name",
                (client_id,),
            )
            return tuple(ClientContactRecord(*row) for row in cursor.fetchall())

    def create_contact(
        self,
        company_id: UUID,
        client_id: UUID,
        actor_id: UUID,
        values: dict[str, object],
    ) -> ClientContactRecord:
        normalized = self._allowed(values, self._contact_columns)
        try:
            with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
                self._lock_client(cursor, company_id, client_id)
                if normalized.get("is_primary") is True:
                    cursor.execute(
                        "UPDATE client_contacts SET is_primary=false,updated_at=NOW() "
                        "WHERE client_id=%s AND is_primary=true",
                        (client_id,),
                    )
                columns = ["id", "client_id", *normalized]
                params = [uuid4(), client_id, *normalized.values()]
                placeholders = ",".join(["%s"] * len(columns))
                cursor.execute(
                    f"INSERT INTO client_contacts({','.join(columns)}) VALUES({placeholders}) "
                    f"RETURNING {self._contact_fields}",
                    params,
                )
                row = cursor.fetchone()
                if row is None:
                    raise RuntimeError("Client contact insert returned no record.")
                self._activity(
                    cursor,
                    company_id,
                    client_id,
                    actor_id,
                    "CONTACT_ADDED",
                    "A client contact was added.",
                )
                return ClientContactRecord(*row)
        except UniqueViolation as error:
            raise ClientConflict("contact_email") from error

    def update_contact(
        self,
        company_id: UUID,
        client_id: UUID,
        contact_id: UUID,
        actor_id: UUID,
        values: dict[str, object],
    ) -> ClientContactRecord | None:
        normalized = self._allowed(values, self._contact_columns)
        try:
            with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
                self._lock_client(cursor, company_id, client_id)
                cursor.execute(
                    "SELECT 1 FROM client_contacts WHERE id=%s AND client_id=%s FOR UPDATE",
                    (contact_id, client_id),
                )
                if cursor.fetchone() is None:
                    return None
                if normalized.get("is_primary") is True:
                    cursor.execute(
                        "UPDATE client_contacts SET is_primary=false,updated_at=NOW() "
                        "WHERE client_id=%s AND id<>%s AND is_primary=true",
                        (client_id, contact_id),
                    )
                if normalized:
                    setters = ",".join(f"{column}=%s" for column in normalized)
                    cursor.execute(
                        f"UPDATE client_contacts SET {setters},updated_at=NOW() "
                        f"WHERE id=%s AND client_id=%s RETURNING {self._contact_fields}",
                        (*normalized.values(), contact_id, client_id),
                    )
                else:
                    cursor.execute(
                        f"SELECT {self._contact_fields} FROM client_contacts "
                        "WHERE id=%s AND client_id=%s",
                        (contact_id, client_id),
                    )
                row = cursor.fetchone()
                if row:
                    self._activity(
                        cursor,
                        company_id,
                        client_id,
                        actor_id,
                        "CONTACT_UPDATED",
                        "A client contact was updated.",
                    )
                return ClientContactRecord(*row) if row else None
        except UniqueViolation as error:
            raise ClientConflict("contact_email") from error

    def list_notes(self, company_id: UUID, client_id: UUID) -> tuple[ClientNoteRecord, ...]:
        with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
            self._lock_client(cursor, company_id, client_id, lock=False)
            cursor.execute(
                f"SELECT {self._note_fields} FROM client_notes note "
                "JOIN users creator ON creator.id=note.created_by_id "
                "WHERE note.company_id=%s AND note.client_id=%s "
                "ORDER BY note.created_at DESC,note.id DESC",
                (company_id, client_id),
            )
            return tuple(ClientNoteRecord(*row) for row in cursor.fetchall())

    def create_note(
        self, company_id: UUID, client_id: UUID, actor_id: UUID, content: str
    ) -> ClientNoteRecord:
        with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
            self._lock_client(cursor, company_id, client_id)
            note_id = uuid4()
            cursor.execute(
                "INSERT INTO client_notes(id,company_id,client_id,created_by_id,content,updated_at) "
                "VALUES(%s,%s,%s,%s,%s,NOW())",
                (note_id, company_id, client_id, actor_id, content),
            )
            self._activity(
                cursor,
                company_id,
                client_id,
                actor_id,
                "NOTE_ADDED",
                "An internal client note was added.",
            )
            return self._get_note(cursor, company_id, client_id, note_id)

    def update_note(
        self, company_id: UUID, client_id: UUID, note_id: UUID, actor_id: UUID, content: str
    ) -> ClientNoteRecord | None:
        with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
            self._lock_client(cursor, company_id, client_id)
            cursor.execute(
                "UPDATE client_notes SET content=%s,updated_at=NOW() "
                "WHERE id=%s AND client_id=%s AND company_id=%s RETURNING id",
                (content, note_id, client_id, company_id),
            )
            if cursor.fetchone() is None:
                return None
            self._activity(
                cursor,
                company_id,
                client_id,
                actor_id,
                "NOTE_UPDATED",
                "An internal client note was updated.",
            )
            return self._get_note(cursor, company_id, client_id, note_id)

    def delete_note(self, company_id: UUID, client_id: UUID, note_id: UUID, actor_id: UUID) -> bool:
        with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
            self._lock_client(cursor, company_id, client_id)
            cursor.execute(
                "DELETE FROM client_notes WHERE id=%s AND client_id=%s AND company_id=%s "
                "RETURNING id",
                (note_id, client_id, company_id),
            )
            if cursor.fetchone() is None:
                return False
            self._activity(
                cursor,
                company_id,
                client_id,
                actor_id,
                "NOTE_DELETED",
                "An internal client note was deleted.",
            )
            return True

    def list_feedback(self, company_id: UUID, client_id: UUID) -> tuple[ClientFeedbackRecord, ...]:
        with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
            self._lock_client(cursor, company_id, client_id, lock=False)
            cursor.execute(
                f"SELECT {self._feedback_fields} FROM client_feedback feedback "
                "JOIN users creator ON creator.id=feedback.created_by_id "
                "WHERE feedback.company_id=%s AND feedback.client_id=%s "
                "ORDER BY feedback.created_at DESC,feedback.id DESC",
                (company_id, client_id),
            )
            return tuple(ClientFeedbackRecord(*row) for row in cursor.fetchall())

    def create_feedback(
        self, company_id: UUID, client_id: UUID, actor_id: UUID, content: str
    ) -> ClientFeedbackRecord:
        with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
            self._lock_client(cursor, company_id, client_id)
            feedback_id = uuid4()
            cursor.execute(
                "INSERT INTO client_feedback(id,company_id,client_id,created_by_id,content,updated_at) "
                "VALUES(%s,%s,%s,%s,%s,NOW())",
                (feedback_id, company_id, client_id, actor_id, content),
            )
            self._activity(
                cursor,
                company_id,
                client_id,
                actor_id,
                "FEEDBACK_ADDED",
                "Client feedback was added.",
            )
            return self._get_feedback(cursor, company_id, client_id, feedback_id)

    def update_feedback(
        self,
        company_id: UUID,
        client_id: UUID,
        feedback_id: UUID,
        actor_id: UUID,
        content: str,
    ) -> ClientFeedbackRecord | None:
        with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
            self._lock_client(cursor, company_id, client_id)
            cursor.execute(
                "UPDATE client_feedback SET content=%s,updated_at=NOW() "
                "WHERE id=%s AND client_id=%s AND company_id=%s RETURNING id",
                (content, feedback_id, client_id, company_id),
            )
            if cursor.fetchone() is None:
                return None
            self._activity(
                cursor,
                company_id,
                client_id,
                actor_id,
                "FEEDBACK_UPDATED",
                "Client feedback was updated.",
            )
            return self._get_feedback(cursor, company_id, client_id, feedback_id)

    def list_activity(self, company_id: UUID, client_id: UUID) -> tuple[ClientActivityRecord, ...]:
        with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
            self._lock_client(cursor, company_id, client_id, lock=False)
            cursor.execute(
                f"SELECT {self._activity_fields} FROM client_activities activity "
                "JOIN users actor ON actor.id=activity.actor_id "
                "WHERE activity.company_id=%s AND activity.client_id=%s "
                "ORDER BY activity.created_at DESC,activity.id DESC",
                (company_id, client_id),
            )
            return tuple(ClientActivityRecord(*row) for row in cursor.fetchall())

    @staticmethod
    def _allowed(values: dict[str, object], allowed: set[str]) -> dict[str, object]:
        return {key: value for key, value in values.items() if key in allowed}

    def _get_client(self, cursor: Any, company_id: UUID, client_id: UUID) -> ClientRecord | None:
        cursor.execute(
            f"SELECT {self._client_fields},"
            "(SELECT CONCAT_WS(' ',contact.first_name,NULLIF(contact.last_name,'')) "
            "FROM client_contacts contact WHERE contact.client_id=clients.id "
            "AND contact.is_primary=true ORDER BY contact.updated_at DESC LIMIT 1),"
            "(SELECT contact.email FROM client_contacts contact "
            "WHERE contact.client_id=clients.id AND contact.is_primary=true "
            "ORDER BY contact.updated_at DESC LIMIT 1),"
            "(SELECT contact.phone FROM client_contacts contact "
            "WHERE contact.client_id=clients.id AND contact.is_primary=true "
            "ORDER BY contact.updated_at DESC LIMIT 1),"
            "(SELECT contact.designation FROM client_contacts contact "
            "WHERE contact.client_id=clients.id AND contact.is_primary=true "
            "ORDER BY contact.updated_at DESC LIMIT 1),"
            "clients.user_id,account_user.name,account_user.email,account_user.status::text "
            "FROM clients LEFT JOIN users account_user ON account_user.id=clients.user_id "
            "WHERE clients.id=%s AND clients.company_id=%s",
            (client_id, company_id),
        )
        row = cursor.fetchone()
        return ClientRecord(*row) if row else None

    @staticmethod
    def _normalize_email(value: object) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip().lower()
        return normalized or None

    @staticmethod
    def _conflict_field(error: UniqueViolation) -> str:
        constraint = error.diag.constraint_name or ""
        if constraint == "clients_company_email_unique_ci":
            return "email"
        if constraint == "clients_user_id_key":
            return "account_user"
        return "code"

    def _ensure_unique_email(
        self,
        cursor: Any,
        company_id: UUID,
        email: object,
        *,
        exclude_client_id: UUID | None = None,
    ) -> None:
        normalized_email = self._normalize_email(email)
        if normalized_email is None:
            return
        cursor.execute(
            "SELECT 1 FROM clients WHERE company_id=%s AND LOWER(email)=LOWER(%s) "
            "AND (%s::uuid IS NULL OR id<>%s) LIMIT 1",
            (company_id, normalized_email, exclude_client_id, exclude_client_id),
        )
        if cursor.fetchone() is not None:
            raise ClientConflict("email")

    def _get_note(
        self, cursor: Any, company_id: UUID, client_id: UUID, note_id: UUID
    ) -> ClientNoteRecord:
        cursor.execute(
            f"SELECT {self._note_fields} FROM client_notes note "
            "JOIN users creator ON creator.id=note.created_by_id "
            "WHERE note.id=%s AND note.client_id=%s AND note.company_id=%s",
            (note_id, client_id, company_id),
        )
        row = cursor.fetchone()
        if row is None:
            raise RuntimeError("Client note write returned no record.")
        return ClientNoteRecord(*row)

    def _get_feedback(
        self, cursor: Any, company_id: UUID, client_id: UUID, feedback_id: UUID
    ) -> ClientFeedbackRecord:
        cursor.execute(
            f"SELECT {self._feedback_fields} FROM client_feedback feedback "
            "JOIN users creator ON creator.id=feedback.created_by_id "
            "WHERE feedback.id=%s AND feedback.client_id=%s AND feedback.company_id=%s",
            (feedback_id, client_id, company_id),
        )
        row = cursor.fetchone()
        if row is None:
            raise RuntimeError("Client feedback write returned no record.")
        return ClientFeedbackRecord(*row)

    @staticmethod
    def _activity(
        cursor: Any,
        company_id: UUID,
        client_id: UUID,
        actor_id: UUID,
        activity_type: str,
        description: str,
    ) -> None:
        cursor.execute(
            "INSERT INTO client_activities(id,company_id,client_id,actor_id,type,description) "
            "VALUES(%s,%s,%s,%s,%s,%s)",
            (uuid4(), company_id, client_id, actor_id, activity_type, description),
        )

    @staticmethod
    def _lock_client(cursor: Any, company_id: UUID, client_id: UUID, *, lock: bool = True) -> None:
        suffix = " FOR UPDATE" if lock else ""
        cursor.execute(
            f"SELECT 1 FROM clients WHERE id=%s AND company_id=%s{suffix}",
            (client_id, company_id),
        )
        if cursor.fetchone() is None:
            raise ClientReferenceError

    def is_ready(self) -> bool:
        try:
            with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
                cursor.execute(
                    "SELECT to_regclass('public.clients') IS NOT NULL AND "
                    "to_regclass('public.client_contacts') IS NOT NULL AND "
                    "to_regclass('public.client_notes') IS NOT NULL AND "
                    "to_regclass('public.client_feedback') IS NOT NULL AND "
                    "to_regclass('public.client_activities') IS NOT NULL"
                )
                row = cursor.fetchone()
                return bool(row and row[0])
        except Exception:
            return False
