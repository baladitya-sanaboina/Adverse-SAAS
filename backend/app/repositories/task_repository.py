"""Database access for production tasks (docs/ProductionManagementPlan.md, section 6)."""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID, uuid4

from app.database.connectivity import database_pool
from app.repositories.package_repository import package_charges_sql
from app.schemas.production import TaskListFilters, WorkerTaskFilters

PricingScope = Literal["CLIENT", "MANAGER"]


def _one(cursor: Any) -> tuple[Any, ...]:
    """Fetch the single row an aggregate query always returns."""
    row = cursor.fetchone()
    if row is None:
        raise RuntimeError("Expected one row from an aggregate query.")
    return tuple(row)


_TASK_COLUMNS = """
    t.id, t.number, t.title, t.description, t.priority::text, t.status::text,
    t.client_id, c.name, c.code,
    t.service_id, s.name, s.code,
    t.assignee_user_id, a.name, t.assignee_type::text,
    t.monitor_user_id, m.name,
    t.due_date, t.currency, t.client_pricing_model::text,
    t.client_price_default, t.client_price_final, t.client_price_reason,
    t.commission_default, t.commission_final, t.commission_reason,
    cb.name, t.created_at, t.updated_at,
    t.assigned_at, t.started_at, t.submitted_at, t.approved_at, t.completed_at, t.cancelled_at,
    (SELECT COUNT(*) FROM task_files tf WHERE tf.task_id = t.id)::int,
    (SELECT COUNT(*) FROM task_comments tc WHERE tc.task_id = t.id)::int,
    t.package_id
"""
_TASK_FROM = """
    FROM tasks t
    JOIN clients c ON c.id = t.client_id
    JOIN company_services s ON s.id = t.service_id
    LEFT JOIN users a ON a.id = t.assignee_user_id
    LEFT JOIN users m ON m.id = t.monitor_user_id
    JOIN users cb ON cb.id = t.created_by_id
"""
# Columns a task mutation may write. Anything else is rejected before SQL is built.
_UPDATABLE_COLUMNS = frozenset(
    {
        "title",
        "description",
        "priority",
        "status",
        "due_date",
        "assignee_user_id",
        "assignee_type",
        "monitor_user_id",
        "client_price_final",
        "client_price_reason",
        "package_id",
        "commission_default",
        "commission_final",
        "commission_reason",
        "assigned_at",
        "started_at",
        "submitted_at",
        "approved_at",
        "completed_at",
        "cancelled_at",
    }
)
_ENUM_CASTS = {
    "priority": '"TaskPriority"',
    "status": '"TaskStatus"',
    "assignee_type": '"TaskAssigneeType"',
}


@dataclass(frozen=True)
class TaskRow:
    id: UUID
    number: int
    title: str
    description: str
    priority: str
    status: str
    client_id: UUID
    client_name: str
    client_code: str
    service_id: UUID
    service_name: str
    service_code: str
    assignee_user_id: UUID | None
    assignee_name: str | None
    assignee_type: str | None
    monitor_user_id: UUID | None
    monitor_name: str | None
    due_date: date | None
    currency: str
    client_pricing_model: str
    client_price_default: Decimal | None
    client_price_final: Decimal
    client_price_reason: str
    commission_default: Decimal | None
    commission_final: Decimal | None
    commission_reason: str
    created_by_name: str
    created_at: datetime
    updated_at: datetime
    assigned_at: datetime | None
    started_at: datetime | None
    submitted_at: datetime | None
    approved_at: datetime | None
    completed_at: datetime | None
    cancelled_at: datetime | None
    files_count: int = 0
    comments_count: int = 0
    package_id: UUID | None = None  # set when a monthly package covered this video

    @property
    def code(self) -> str:
        return f"TSK-{self.number:04d}"


@dataclass(frozen=True)
class ClientRef:
    id: UUID
    name: str
    code: str
    status: str


@dataclass(frozen=True)
class ServiceRef:
    id: UUID
    name: str
    code: str
    status: str
    client_pricing_model: str


@dataclass(frozen=True)
class PersonRow:
    id: UUID
    name: str
    role: str  # MANAGER or EMPLOYEE
    code: str
    email: str


@dataclass(frozen=True)
class HistoryRow:
    id: UUID
    from_status: str | None
    to_status: str
    note: str
    actor_name: str
    created_at: datetime


@dataclass(frozen=True)
class PriceChangeRow:
    id: UUID
    field: str
    old_amount: Decimal | None
    new_amount: Decimal | None
    reason: str
    actor_name: str
    created_at: datetime


@dataclass(frozen=True)
class CommentRow:
    id: UUID
    author_id: UUID
    author_name: str
    content: str
    created_at: datetime


@dataclass(frozen=True)
class FileRow:
    id: UUID
    task_id: UUID
    kind: str
    file_name: str
    storage_path: str
    mime_type: str
    size_bytes: int
    uploaded_by_id: UUID
    uploaded_by_name: str
    created_at: datetime


@dataclass(frozen=True)
class BudgetTotals:
    total: Decimal
    used: Decimal
    committed: Decimal


@dataclass
class TaskMutation:
    """Changes to apply to a locked task row in one transaction."""

    updates: dict[str, Any] = field(default_factory=dict)
    status_change: tuple[str | None, str, str] | None = None  # (from, to, note)
    price_changes: list[tuple[str, Decimal | None, Decimal | None, str]] = field(
        default_factory=list
    )  # (field, old, new, reason)


class TaskNotFound(Exception):
    pass


class TaskRepository:
    @staticmethod
    def _task(row: tuple[Any, ...]) -> TaskRow:
        return TaskRow(*row)

    # -- reference lookups ---------------------------------------------------------------

    def company_currency(self, company_id: UUID) -> str:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            return self._company_currency(cursor, company_id)

    @staticmethod
    def _company_currency(cursor: Any, company_id: UUID) -> str:
        cursor.execute(
            "SELECT COALESCE(NULLIF(currency,''),'INR') FROM company_tenant_defaults "
            "WHERE company_id=%s",
            (company_id,),
        )
        row = cursor.fetchone()
        return str(row[0]).upper() if row and row[0] else "INR"

    def get_client(self, company_id: UUID, client_id: UUID) -> ClientRef | None:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT id,name,code,status::text FROM clients WHERE id=%s AND company_id=%s",
                (client_id, company_id),
            )
            row = cursor.fetchone()
            return ClientRef(*row) if row else None

    def get_client_for_user(self, company_id: UUID, user_id: UUID) -> ClientRef | None:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT id,name,code,status::text FROM clients WHERE user_id=%s AND company_id=%s",
                (user_id, company_id),
            )
            row = cursor.fetchone()
            return ClientRef(*row) if row else None

    def get_service(self, company_id: UUID, service_id: UUID) -> ServiceRef | None:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT id,name,code,status::text,client_pricing_model::text "
                "FROM company_services WHERE id=%s AND company_id=%s",
                (service_id, company_id),
            )
            row = cursor.fetchone()
            return ServiceRef(*row) if row else None

    _PERSON_SQL = """
        SELECT u.id, u.name,
            CASE r.code WHEN 'COMPANY_MANAGER' THEN 'MANAGER' ELSE 'EMPLOYEE' END,
            COALESCE(e.employee_code, ''), u.email
        FROM users u
        JOIN roles r ON r.id = u.role_id
        LEFT JOIN employees e ON e.user_id = u.id AND e.company_id = u.company_id
        WHERE u.company_id = %s
          AND r.code IN ('COMPANY_MANAGER', 'COMPANY_EMPLOYEE')
          AND u.status IN ('ACTIVE', 'PENDING_VERIFICATION')
    """

    def get_person(self, company_id: UUID, user_id: UUID) -> PersonRow | None:
        """An active Manager or Employee of the company."""
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(self._PERSON_SQL + " AND u.id = %s", (company_id, user_id))
            row = cursor.fetchone()
            return PersonRow(*row) if row else None

    def get_person_any_status(self, company_id: UUID, user_id: UUID) -> PersonRow | None:
        """A Manager or Employee of the company, including deactivated people (for history)."""
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT u.id, u.name,
                    CASE r.code WHEN 'COMPANY_MANAGER' THEN 'MANAGER' ELSE 'EMPLOYEE' END,
                    COALESCE(e.employee_code, ''), u.email
                FROM users u
                JOIN roles r ON r.id = u.role_id
                LEFT JOIN employees e ON e.user_id = u.id AND e.company_id = u.company_id
                WHERE u.company_id = %s AND u.id = %s
                  AND r.code IN ('COMPANY_MANAGER', 'COMPANY_EMPLOYEE')
                """,
                (company_id, user_id),
            )
            row = cursor.fetchone()
            return PersonRow(*row) if row else None

    def list_people(self, company_id: UUID) -> list[PersonRow]:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(self._PERSON_SQL + " ORDER BY u.name", (company_id,))
            return [PersonRow(*row) for row in cursor.fetchall()]

    def current_rate(
        self, company_id: UUID, scope: PricingScope, subject_id: UUID, service_id: UUID
    ) -> Decimal | None:
        """The configured rate in effect right now (client price or manager commission)."""
        subject_column = "client_id" if scope == "CLIENT" else "manager_user_id"
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT amount FROM service_pricing
                WHERE company_id=%s AND scope=%s::"ServicePricingScope"
                  AND {subject_column}=%s AND service_id=%s
                  AND effective_from <= NOW()
                  AND (effective_to IS NULL OR effective_to > NOW())
                ORDER BY effective_from DESC, created_at DESC
                LIMIT 1
                """,
                (company_id, scope, subject_id, service_id),
            )
            row = cursor.fetchone()
            return Decimal(row[0]) if row else None

    def calendar_service_choices(self, company_id: UUID, client_id: UUID) -> list[UUID]:
        """Active services, the ones this client has used most first (Phase 13 tickets)."""
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT s.id FROM company_services s
                WHERE s.company_id = %(company)s AND s.status::text = 'ACTIVE'
                ORDER BY (
                  SELECT COUNT(*) FROM tasks t
                  WHERE t.company_id = %(company)s AND t.client_id = %(client)s
                    AND t.service_id = s.id
                ) DESC, s.name
                """,
                {"company": company_id, "client": client_id},
            )
            return [row[0] for row in cursor.fetchall()]

    def budget_totals(
        self, company_id: UUID, client_id: UUID, exclude_task_id: UUID | None = None
    ) -> BudgetTotals:
        """Budget total, used (approved work) and committed (open work) for one client."""
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT
                  (SELECT COALESCE(SUM(amount),0) FROM client_budget_entries
                     WHERE company_id=%(company)s AND client_id=%(client)s),
                  COALESCE(SUM(client_price_final) FILTER (
                     WHERE status IN ('APPROVED','COMPLETED')),0)
                  + (SELECT COALESCE(SUM(pk.amount),0) FROM {package_charges_sql()} pk
                     WHERE pk.client_id = %(client)s),
                  COALESCE(SUM(client_price_final) FILTER (
                     WHERE status NOT IN ('APPROVED','COMPLETED','CANCELLED')),0)
                FROM tasks
                WHERE company_id=%(company)s AND client_id=%(client)s
                  AND (%(exclude)s::uuid IS NULL OR id <> %(exclude)s::uuid)
                """,
                {"company": company_id, "client": client_id, "exclude": exclude_task_id},
            )
            row = _one(cursor)
            return BudgetTotals(Decimal(row[0]), Decimal(row[1]), Decimal(row[2]))

    # -- reads -----------------------------------------------------------------------------

    def get_task(self, company_id: UUID, task_id: UUID) -> TaskRow | None:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                f"SELECT {_TASK_COLUMNS} {_TASK_FROM} WHERE t.company_id=%s AND t.id=%s",
                (company_id, task_id),
            )
            row = cursor.fetchone()
            return self._task(row) if row else None

    def list_tasks(
        self, company_id: UUID, filters: TaskListFilters, today: date
    ) -> tuple[list[TaskRow], int]:
        clauses = ["t.company_id = %(company)s"]
        params: dict[str, Any] = {"company": company_id, "today": today}
        if filters.status:
            clauses.append('t.status = %(status)s::"TaskStatus"')
            params["status"] = filters.status
        if filters.client_id:
            clauses.append("t.client_id = %(client)s")
            params["client"] = filters.client_id
        if filters.service_id:
            clauses.append("t.service_id = %(service)s")
            params["service"] = filters.service_id
        if filters.assignee_user_id:
            clauses.append("t.assignee_user_id = %(assignee)s")
            params["assignee"] = filters.assignee_user_id
        if filters.overdue_only:
            clauses.append(
                "t.due_date < %(today)s AND t.status NOT IN ('APPROVED','COMPLETED','CANCELLED')"
            )
        if filters.search:
            clauses.append(
                "(t.title ILIKE %(search)s OR c.name ILIKE %(search)s "
                "OR ('TSK-' || LPAD(t.number::text, 4, '0')) ILIKE %(search)s)"
            )
            params["search"] = f"%{filters.search}%"
        return self._page(clauses, params, filters.page, filters.page_size)

    def list_worker_tasks(
        self, company_id: UUID, user_id: UUID, filters: WorkerTaskFilters
    ) -> tuple[list[TaskRow], int]:
        clauses = ["t.company_id = %(company)s"]
        params: dict[str, Any] = {"company": company_id, "user": user_id}
        if filters.role == "ASSIGNEE":
            clauses.append("t.assignee_user_id = %(user)s")
        elif filters.role == "MONITOR":
            clauses.append("t.monitor_user_id = %(user)s")
        else:
            clauses.append("(t.assignee_user_id = %(user)s OR t.monitor_user_id = %(user)s)")
        if filters.status:
            clauses.append('t.status = %(status)s::"TaskStatus"')
            params["status"] = filters.status
        if filters.search:
            clauses.append("(t.title ILIKE %(search)s OR c.name ILIKE %(search)s)")
            params["search"] = f"%{filters.search}%"
        return self._page(clauses, params, filters.page, filters.page_size)

    def focus(self, company_id: UUID, user_id: UUID | None, until: date) -> list[TaskRow]:
        """Open tasks due up to `until` (overdue included) and tasks waiting for review, most
        urgent first (owner request 2026-11-19). user_id None: every task (admin); otherwise
        the tasks this person is assigned to or monitors."""
        clauses = [
            "t.company_id = %(company)s",
            "t.status NOT IN ('APPROVED','COMPLETED','CANCELLED')",
            "(t.due_date <= %(until)s OR t.status IN ('SUBMITTED','REVIEW'))",
        ]
        params: dict[str, Any] = {"company": company_id, "until": until, "user": user_id}
        if user_id is not None:
            clauses.append("(t.assignee_user_id = %(user)s OR t.monitor_user_id = %(user)s)")
        where = " AND ".join(clauses)
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT {_TASK_COLUMNS} {_TASK_FROM} WHERE {where}
                ORDER BY
                  CASE t.priority WHEN 'URGENT' THEN 0 WHEN 'HIGH' THEN 1
                    WHEN 'MEDIUM' THEN 2 ELSE 3 END,
                  t.due_date ASC NULLS LAST, t.number
                LIMIT 300
                """,
                params,
            )
            return [self._task(row) for row in cursor.fetchall()]

    def _page(
        self, clauses: list[str], params: dict[str, Any], page: int, page_size: int
    ) -> tuple[list[TaskRow], int]:
        where = " AND ".join(clauses)
        params = {**params, "limit": page_size, "offset": (page - 1) * page_size}
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(f"SELECT COUNT(*) {_TASK_FROM} WHERE {where}", params)
            total = int(_one(cursor)[0])
            cursor.execute(
                f"""
                SELECT {_TASK_COLUMNS} {_TASK_FROM} WHERE {where}
                ORDER BY
                  CASE WHEN t.status IN ('APPROVED','COMPLETED','CANCELLED') THEN 1 ELSE 0 END,
                  t.due_date ASC NULLS LAST, t.created_at DESC
                LIMIT %(limit)s OFFSET %(offset)s
                """,
                params,
            )
            return [self._task(row) for row in cursor.fetchall()], total

    def list_history(self, task_id: UUID) -> list[HistoryRow]:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT h.id,h.from_status::text,h.to_status::text,h.note,u.name,h.created_at "
                "FROM task_status_history h JOIN users u ON u.id=h.actor_id "
                "WHERE h.task_id=%s ORDER BY h.created_at, h.id",
                (task_id,),
            )
            return [HistoryRow(*row) for row in cursor.fetchall()]

    def list_price_changes(self, task_id: UUID) -> list[PriceChangeRow]:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT p.id,p.field::text,p.old_amount,p.new_amount,p.reason,u.name,p.created_at "
                "FROM task_price_changes p JOIN users u ON u.id=p.actor_id "
                "WHERE p.task_id=%s ORDER BY p.created_at, p.id",
                (task_id,),
            )
            return [PriceChangeRow(*row) for row in cursor.fetchall()]

    def list_comments(self, task_id: UUID) -> list[CommentRow]:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT tc.id,tc.author_id,u.name,tc.content,tc.created_at "
                "FROM task_comments tc JOIN users u ON u.id=tc.author_id "
                "WHERE tc.task_id=%s ORDER BY tc.created_at, tc.id",
                (task_id,),
            )
            return [CommentRow(*row) for row in cursor.fetchall()]

    _FILE_SELECT = (
        "SELECT f.id,f.task_id,f.kind::text,f.file_name,f.storage_path,f.mime_type,f.size_bytes,"
        "f.uploaded_by_id,u.name,f.created_at FROM task_files f JOIN users u ON u.id=f.uploaded_by_id "
    )

    def list_files(self, task_id: UUID) -> list[FileRow]:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                self._FILE_SELECT + "WHERE f.task_id=%s ORDER BY f.kind, f.created_at",
                (task_id,),
            )
            return [FileRow(*row) for row in cursor.fetchall()]

    def get_file(self, company_id: UUID, task_id: UUID, file_id: UUID) -> FileRow | None:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                self._FILE_SELECT + "WHERE f.company_id=%s AND f.task_id=%s AND f.id=%s",
                (company_id, task_id, file_id),
            )
            row = cursor.fetchone()
            return FileRow(*row) if row else None

    # -- writes ----------------------------------------------------------------------------

    def create_task(
        self,
        company_id: UUID,
        actor_id: UUID,
        values: dict[str, Any],
        price_changes: list[tuple[str, Decimal | None, Decimal | None, str]],
    ) -> UUID:
        """Insert a task with the next per-company number, its first status entry and any
        manual price changes, all in one transaction."""
        task_id = uuid4()
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            # Serialize numbering per company so two tasks never get the same number.
            cursor.execute(
                "SELECT pg_advisory_xact_lock(hashtext('tasks:' || %s::text))", (company_id,)
            )
            cursor.execute(
                "SELECT COALESCE(MAX(number),0)+1 FROM tasks WHERE company_id=%s", (company_id,)
            )
            number = int(_one(cursor)[0])
            currency = self._company_currency(cursor, company_id)
            cursor.execute(
                """
                INSERT INTO tasks(
                    id, company_id, number, client_id, service_id, title, description,
                    priority, status, assignee_user_id, assignee_type, monitor_user_id, due_date,
                    currency, client_pricing_model, client_price_default, client_price_final,
                    client_price_reason, commission_default, commission_final, commission_reason,
                    created_by_id, assigned_at, created_at, updated_at
                ) VALUES (
                    %(id)s, %(company)s, %(number)s, %(client_id)s, %(service_id)s, %(title)s,
                    %(description)s, %(priority)s::"TaskPriority", %(status)s::"TaskStatus",
                    %(assignee_user_id)s, %(assignee_type)s::"TaskAssigneeType",
                    %(monitor_user_id)s, %(due_date)s, %(currency)s,
                    %(client_pricing_model)s::"ServicePricingModel", %(client_price_default)s,
                    %(client_price_final)s, %(client_price_reason)s, %(commission_default)s,
                    %(commission_final)s, %(commission_reason)s, %(actor)s, %(assigned_at)s,
                    NOW(), NOW()
                )
                """,
                {
                    **values,
                    "id": task_id,
                    "company": company_id,
                    "number": number,
                    "currency": currency,
                    "actor": actor_id,
                },
            )
            self._insert_history(
                cursor, company_id, task_id, actor_id, None, str(values["status"]), "Task created"
            )
            for change in price_changes:
                self._insert_price_change(cursor, company_id, task_id, actor_id, change)
        return task_id

    def mutate_task(
        self,
        company_id: UUID,
        task_id: UUID,
        actor_id: UUID,
        plan: Callable[[TaskRow], TaskMutation],
    ) -> None:
        """Lock the task, let ``plan`` decide the change (it may raise to abort), then apply it.

        Locking first means two people acting at once cannot both move the task from the same
        status or both approve it.
        """
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                f"SELECT {_TASK_COLUMNS} {_TASK_FROM} "
                "WHERE t.company_id=%s AND t.id=%s FOR UPDATE OF t",
                (company_id, task_id),
            )
            row = cursor.fetchone()
            if row is None:
                raise TaskNotFound()
            mutation = plan(self._task(row))
            if mutation.updates:
                unknown = set(mutation.updates) - _UPDATABLE_COLUMNS
                if unknown:
                    raise ValueError(f"Columns not allowed: {sorted(unknown)}")
                assignments = []
                for column in mutation.updates:
                    cast = f"::{_ENUM_CASTS[column]}" if column in _ENUM_CASTS else ""
                    assignments.append(f"{column} = %({column})s{cast}")
                cursor.execute(
                    f"UPDATE tasks SET {', '.join(assignments)}, updated_at = NOW() "
                    "WHERE id = %(task_id)s",
                    {**mutation.updates, "task_id": task_id},
                )
            if mutation.status_change is not None:
                from_status, to_status, note = mutation.status_change
                self._insert_history(
                    cursor, company_id, task_id, actor_id, from_status, to_status, note
                )
            for change in mutation.price_changes:
                self._insert_price_change(cursor, company_id, task_id, actor_id, change)

    def add_comment(self, company_id: UUID, task_id: UUID, author_id: UUID, content: str) -> None:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO task_comments(id,company_id,task_id,author_id,content,created_at,"
                "updated_at) VALUES(%s,%s,%s,%s,%s,NOW(),NOW())",
                (uuid4(), company_id, task_id, author_id, content),
            )

    def add_file(
        self,
        company_id: UUID,
        task_id: UUID,
        uploader_id: UUID,
        kind: str,
        file_name: str,
        storage_path: str,
        mime_type: str,
        size_bytes: int,
    ) -> UUID:
        file_id = uuid4()
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO task_files(id,company_id,task_id,kind,file_name,storage_path,"
                'mime_type,size_bytes,uploaded_by_id,created_at) VALUES(%s,%s,%s,%s::"TaskFileKind",'
                "%s,%s,%s,%s,%s,NOW())",
                (
                    file_id,
                    company_id,
                    task_id,
                    kind,
                    file_name,
                    storage_path,
                    mime_type,
                    size_bytes,
                    uploader_id,
                ),
            )
        return file_id

    def delete_file(self, company_id: UUID, file_id: UUID) -> None:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM task_files WHERE company_id=%s AND id=%s", (company_id, file_id)
            )

    @staticmethod
    def _insert_history(
        cursor: Any,
        company_id: UUID,
        task_id: UUID,
        actor_id: UUID,
        from_status: str | None,
        to_status: str,
        note: str,
    ) -> None:
        cursor.execute(
            "INSERT INTO task_status_history(id,company_id,task_id,from_status,to_status,actor_id,"
            'note,created_at) VALUES(%s,%s,%s,%s::"TaskStatus",%s::"TaskStatus",%s,%s,NOW())',
            (uuid4(), company_id, task_id, from_status, to_status, actor_id, note),
        )

    @staticmethod
    def _insert_price_change(
        cursor: Any,
        company_id: UUID,
        task_id: UUID,
        actor_id: UUID,
        change: tuple[str, Decimal | None, Decimal | None, str],
    ) -> None:
        field_name, old_amount, new_amount, reason = change
        cursor.execute(
            "INSERT INTO task_price_changes(id,company_id,task_id,field,old_amount,new_amount,"
            'reason,actor_id,created_at) VALUES(%s,%s,%s,%s::"TaskPriceField",%s,%s,%s,%s,NOW())',
            (uuid4(), company_id, task_id, field_name, old_amount, new_amount, reason, actor_id),
        )

    def is_ready(self) -> bool:
        try:
            with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
                cursor.execute("SELECT to_regclass('public.tasks') IS NOT NULL")
                row = cursor.fetchone()
                return bool(row and row[0])
        except Exception:
            return False
