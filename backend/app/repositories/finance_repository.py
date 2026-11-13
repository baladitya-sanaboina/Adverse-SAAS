"""Database access for budgets, payments, salaries, payouts and money reports.

Task timestamps are stored in UTC; date filters convert them to the company timezone so that
"today" and "this month" match the owner's calendar.
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from psycopg.errors import UniqueViolation

from app.database.connectivity import database_pool
from app.schemas.production import PaymentListFilters

_BILLABLE = "('APPROVED','COMPLETED')"
_CLOSED = "('APPROVED','COMPLETED','CANCELLED')"


def _one(cursor: Any) -> tuple[Any, ...]:
    """Fetch the single row an aggregate query always returns."""
    row = cursor.fetchone()
    if row is None:
        raise RuntimeError("Expected one row from an aggregate query.")
    return tuple(row)


def _local_date(column: str) -> str:
    """SQL expression for a UTC timestamp column as a date in the company timezone."""
    return f"(({column}) AT TIME ZONE 'UTC' AT TIME ZONE %(tz)s)::date"


def _range_sql(expression: str, start: date | None, end: date | None) -> str:
    parts = []
    if start is not None:
        parts.append(f"{expression} >= %(start)s")
    if end is not None:
        parts.append(f"{expression} <= %(end)s")
    return " AND ".join(parts) if parts else "TRUE"


@dataclass(frozen=True)
class BudgetEntryRow:
    id: UUID
    type: str
    amount: Decimal
    currency: str
    note: str
    created_by_name: str
    created_at: datetime


@dataclass(frozen=True)
class ClientPaymentRow:
    id: UUID
    client_id: UUID
    client_name: str
    client_code: str
    amount: Decimal
    currency: str
    received_on: date
    method: str
    reference: str
    note: str
    created_by_name: str
    created_at: datetime


@dataclass(frozen=True)
class SalaryRecordRow:
    id: UUID
    user_id: UUID
    monthly_amount: Decimal
    currency: str
    effective_from: date
    effective_to: date | None
    note: str
    created_by_name: str
    created_at: datetime


@dataclass(frozen=True)
class SalaryPaymentRow:
    id: UUID
    user_id: UUID
    employee_name: str
    period_month: date
    amount: Decimal
    currency: str
    paid_on: date
    method: str
    reference: str
    note: str
    created_by_name: str
    created_at: datetime


@dataclass(frozen=True)
class PayoutRow:
    id: UUID
    manager_user_id: UUID
    manager_name: str
    amount: Decimal
    currency: str
    paid_on: date
    method: str
    reference: str
    note: str
    created_by_name: str
    created_at: datetime


@dataclass(frozen=True)
class CommissionTaskRow:
    task_id: UUID
    number: int
    title: str
    service_name: str
    status: str
    commission: Decimal
    approved_at: datetime | None


@dataclass(frozen=True)
class ServiceCountRow:
    service_id: UUID
    service_name: str
    service_code: str
    completed: int
    in_progress: int
    charged: Decimal
    commission: Decimal


@dataclass(frozen=True)
class ClientBalanceRow:
    client_id: UUID
    client_name: str
    client_code: str
    total_tasks: int
    completed_tasks: int
    open_tasks: int
    billed_in_range: Decimal
    received_in_range: Decimal
    billed_all_time: Decimal
    received_all_time: Decimal
    budget_total: Decimal


@dataclass(frozen=True)
class PersonWorkRow:
    user_id: UUID
    name: str
    role: str
    total_tasks: int
    completed_tasks: int
    open_tasks: int
    commission_in_range: Decimal
    commission_all_time: Decimal
    payouts_in_range: Decimal
    payouts_all_time: Decimal
    salary_paid_in_range: Decimal
    salary_paid_all_time: Decimal


@dataclass(frozen=True)
class TaskCountsRow:
    open_tasks: int
    unassigned: int
    in_review: int
    overdue: int


@dataclass(frozen=True)
class AttentionTaskRow:
    id: UUID
    number: int
    title: str
    client_name: str
    assignee_name: str | None
    due_date: date
    status: str


class SalaryDateConflict(Exception):
    pass


class FinanceRepository:
    # -- company settings ----------------------------------------------------------------

    def company_timezone(self, company_id: UUID) -> str:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT COALESCE(NULLIF(d.timezone,''), NULLIF(c.timezone,''), 'UTC') "
                "FROM companies c LEFT JOIN company_tenant_defaults d ON d.company_id=c.id "
                "WHERE c.id=%s",
                (company_id,),
            )
            row = cursor.fetchone()
            return str(row[0]) if row else "UTC"

    def company_currency(self, company_id: UUID) -> str:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            return self._currency(cursor, company_id)

    @staticmethod
    def _currency(cursor: Any, company_id: UUID) -> str:
        cursor.execute(
            "SELECT COALESCE(NULLIF(currency,''),'INR') FROM company_tenant_defaults "
            "WHERE company_id=%s",
            (company_id,),
        )
        row = cursor.fetchone()
        return str(row[0]).upper() if row and row[0] else "INR"

    @staticmethod
    def _audit(
        cursor: Any, actor_id: UUID, company_id: UUID, action: str, details: dict[str, str]
    ) -> None:
        from psycopg.types.json import Jsonb

        cursor.execute(
            "INSERT INTO company_setting_audits(id,actor_id,company_id,action,details,created_at)"
            " VALUES(%s,%s,%s,%s,%s,NOW())",
            (uuid4(), actor_id, company_id, action, Jsonb(details)),
        )

    # -- client budgets ------------------------------------------------------------------

    def list_budget_entries(self, company_id: UUID, client_id: UUID) -> list[BudgetEntryRow]:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT b.id,b.type::text,b.amount,b.currency,b.note,u.name,b.created_at "
                "FROM client_budget_entries b JOIN users u ON u.id=b.created_by_id "
                "WHERE b.company_id=%s AND b.client_id=%s ORDER BY b.created_at DESC",
                (company_id, client_id),
            )
            return [BudgetEntryRow(*row) for row in cursor.fetchall()]

    def add_budget_entry(
        self,
        company_id: UUID,
        client_id: UUID,
        actor_id: UUID,
        entry_type: str,
        amount: Decimal,
        note: str,
    ) -> None:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            currency = self._currency(cursor, company_id)
            cursor.execute(
                "INSERT INTO client_budget_entries(id,company_id,client_id,type,amount,currency,"
                'note,created_by_id,created_at) VALUES(%s,%s,%s,%s::"ClientBudgetEntryType",'
                "%s,%s,%s,%s,NOW())",
                (uuid4(), company_id, client_id, entry_type, amount, currency, note, actor_id),
            )
            self._audit(
                cursor,
                actor_id,
                company_id,
                "CLIENT_BUDGET_ENTRY_ADDED",
                {"client_id": str(client_id), "type": entry_type, "amount": str(amount)},
            )

    # -- client payments -----------------------------------------------------------------

    _CLIENT_PAYMENT_SELECT = """
        SELECT p.id,p.client_id,c.name,c.code,p.amount,p.currency,p.received_on,p.method::text,
            p.reference,p.note,u.name,p.created_at
        FROM client_payments p
        JOIN clients c ON c.id=p.client_id
        JOIN users u ON u.id=p.created_by_id
    """

    def list_client_payments(
        self, company_id: UUID, filters: PaymentListFilters
    ) -> tuple[list[ClientPaymentRow], int, Decimal]:
        where, params = self._payment_where("p", "client_id", "received_on", company_id, filters)
        return self._paged(
            self._CLIENT_PAYMENT_SELECT,
            "FROM client_payments p",
            where,
            params,
            "p.received_on DESC, p.created_at DESC",
            filters,
            ClientPaymentRow,
        )

    def list_client_payments_for_client(
        self, company_id: UUID, client_id: UUID
    ) -> list[ClientPaymentRow]:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                self._CLIENT_PAYMENT_SELECT
                + "WHERE p.company_id=%s AND p.client_id=%s ORDER BY p.received_on DESC",
                (company_id, client_id),
            )
            return [ClientPaymentRow(*row) for row in cursor.fetchall()]

    def get_client_payment(self, company_id: UUID, payment_id: UUID) -> ClientPaymentRow | None:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                self._CLIENT_PAYMENT_SELECT + "WHERE p.company_id=%s AND p.id=%s",
                (company_id, payment_id),
            )
            row = cursor.fetchone()
            return ClientPaymentRow(*row) if row else None

    def create_client_payment(
        self, company_id: UUID, actor_id: UUID, values: dict[str, Any]
    ) -> UUID:
        payment_id = uuid4()
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            currency = self._currency(cursor, company_id)
            cursor.execute(
                "INSERT INTO client_payments(id,company_id,client_id,amount,currency,received_on,"
                "method,reference,note,created_by_id,created_at,updated_at) VALUES(%s,%s,%s,%s,%s,"
                '%s,%s::"PaymentMethod",%s,%s,%s,NOW(),NOW())',
                (
                    payment_id,
                    company_id,
                    values["client_id"],
                    values["amount"],
                    currency,
                    values["received_on"],
                    values["method"],
                    values["reference"],
                    values["note"],
                    actor_id,
                ),
            )
            self._audit(
                cursor,
                actor_id,
                company_id,
                "CLIENT_PAYMENT_RECORDED",
                {"payment_id": str(payment_id), "amount": str(values["amount"])},
            )
        return payment_id

    def delete_payment(
        self, table: str, company_id: UUID, payment_id: UUID, actor_id: UUID
    ) -> bool:
        if table not in {"client_payments", "salary_payments", "manager_payouts"}:
            raise ValueError("Unknown payment table.")
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                f"DELETE FROM {table} WHERE company_id=%s AND id=%s RETURNING amount",
                (company_id, payment_id),
            )
            row = cursor.fetchone()
            if row is None:
                return False
            self._audit(
                cursor,
                actor_id,
                company_id,
                f"{table.upper()}_DELETED",
                {"payment_id": str(payment_id), "amount": str(row[0])},
            )
            return True

    # -- salaries ------------------------------------------------------------------------

    def list_salary_records(self, company_id: UUID, user_id: UUID | None) -> list[SalaryRecordRow]:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT s.id,s.user_id,s.monthly_amount,s.currency,s.effective_from,s.effective_to,"
                "s.note,u.name,s.created_at FROM employee_salaries s "
                "JOIN users u ON u.id=s.created_by_id "
                "WHERE s.company_id=%(company)s AND (%(user)s::uuid IS NULL OR s.user_id=%(user)s::uuid) "
                "ORDER BY s.user_id, s.effective_from DESC",
                {"company": company_id, "user": user_id},
            )
            return [SalaryRecordRow(*row) for row in cursor.fetchall()]

    def set_salary(
        self,
        company_id: UUID,
        actor_id: UUID,
        user_id: UUID,
        monthly_amount: Decimal,
        effective_from: date,
        note: str,
    ) -> None:
        """Add a salary from ``effective_from`` while keeping earlier salaries as history.

        A salary on the same start date is corrected in place.
        """
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT id,effective_from,effective_to FROM employee_salaries "
                "WHERE company_id=%s AND user_id=%s ORDER BY effective_from FOR UPDATE",
                (company_id, user_id),
            )
            rows = cursor.fetchall()
            same_day = next((row for row in rows if row[1] == effective_from), None)
            if same_day is not None:
                cursor.execute(
                    "UPDATE employee_salaries SET monthly_amount=%s, note=%s WHERE id=%s",
                    (monthly_amount, note, same_day[0]),
                )
            else:
                previous = [row for row in rows if row[1] < effective_from]
                following = [row for row in rows if row[1] > effective_from]
                if previous:
                    last = previous[-1]
                    if last[2] is None or last[2] > effective_from:
                        cursor.execute(
                            "UPDATE employee_salaries SET effective_to=%s WHERE id=%s",
                            (effective_from, last[0]),
                        )
                effective_to = following[0][1] if following else None
                currency = self._currency(cursor, company_id)
                try:
                    cursor.execute(
                        "INSERT INTO employee_salaries(id,company_id,user_id,monthly_amount,"
                        "currency,effective_from,effective_to,note,created_by_id,created_at) "
                        "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())",
                        (
                            uuid4(),
                            company_id,
                            user_id,
                            monthly_amount,
                            currency,
                            effective_from,
                            effective_to,
                            note,
                            actor_id,
                        ),
                    )
                except UniqueViolation as error:
                    raise SalaryDateConflict() from error
            self._audit(
                cursor,
                actor_id,
                company_id,
                "EMPLOYEE_SALARY_SET",
                {
                    "user_id": str(user_id),
                    "monthly_amount": str(monthly_amount),
                    "effective_from": effective_from.isoformat(),
                },
            )

    _SALARY_PAYMENT_SELECT = """
        SELECT p.id,p.user_id,e.name,p.period_month,p.amount,p.currency,p.paid_on,p.method::text,
            p.reference,p.note,u.name,p.created_at
        FROM salary_payments p
        JOIN users e ON e.id=p.user_id
        JOIN users u ON u.id=p.created_by_id
    """

    def list_salary_payments(
        self, company_id: UUID, filters: PaymentListFilters
    ) -> tuple[list[SalaryPaymentRow], int, Decimal]:
        where, params = self._payment_where("p", "user_id", "paid_on", company_id, filters)
        return self._paged(
            self._SALARY_PAYMENT_SELECT,
            "FROM salary_payments p",
            where,
            params,
            "p.paid_on DESC, p.created_at DESC",
            filters,
            SalaryPaymentRow,
        )

    def list_salary_payments_for(self, company_id: UUID, user_id: UUID) -> list[SalaryPaymentRow]:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                self._SALARY_PAYMENT_SELECT
                + "WHERE p.company_id=%s AND p.user_id=%s ORDER BY p.period_month DESC, p.paid_on DESC",
                (company_id, user_id),
            )
            return [SalaryPaymentRow(*row) for row in cursor.fetchall()]

    def get_salary_payment(self, company_id: UUID, payment_id: UUID) -> SalaryPaymentRow | None:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                self._SALARY_PAYMENT_SELECT + "WHERE p.company_id=%s AND p.id=%s",
                (company_id, payment_id),
            )
            row = cursor.fetchone()
            return SalaryPaymentRow(*row) if row else None

    def create_salary_payment(
        self, company_id: UUID, actor_id: UUID, values: dict[str, Any]
    ) -> UUID:
        payment_id = uuid4()
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            currency = self._currency(cursor, company_id)
            cursor.execute(
                "INSERT INTO salary_payments(id,company_id,user_id,period_month,amount,currency,"
                "paid_on,method,reference,note,created_by_id,created_at,updated_at) VALUES(%s,%s,"
                '%s,%s,%s,%s,%s,%s::"PaymentMethod",%s,%s,%s,NOW(),NOW())',
                (
                    payment_id,
                    company_id,
                    values["user_id"],
                    values["period_month"],
                    values["amount"],
                    currency,
                    values["paid_on"],
                    values["method"],
                    values["reference"],
                    values["note"],
                    actor_id,
                ),
            )
            self._audit(
                cursor,
                actor_id,
                company_id,
                "SALARY_PAYMENT_RECORDED",
                {"payment_id": str(payment_id), "amount": str(values["amount"])},
            )
        return payment_id

    def salary_paid_by_month(self, company_id: UUID, user_id: UUID) -> dict[date, Decimal]:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT period_month, SUM(amount) FROM salary_payments "
                "WHERE company_id=%s AND user_id=%s GROUP BY period_month",
                (company_id, user_id),
            )
            return {row[0]: Decimal(row[1]) for row in cursor.fetchall()}

    def salary_paid_totals(self, company_id: UUID) -> dict[UUID, Decimal]:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT user_id, SUM(amount) FROM salary_payments WHERE company_id=%s "
                "GROUP BY user_id",
                (company_id,),
            )
            return {row[0]: Decimal(row[1]) for row in cursor.fetchall()}

    # -- manager payouts -----------------------------------------------------------------

    _PAYOUT_SELECT = """
        SELECT p.id,p.manager_user_id,m.name,p.amount,p.currency,p.paid_on,p.method::text,
            p.reference,p.note,u.name,p.created_at
        FROM manager_payouts p
        JOIN users m ON m.id=p.manager_user_id
        JOIN users u ON u.id=p.created_by_id
    """

    def list_payouts(
        self, company_id: UUID, filters: PaymentListFilters
    ) -> tuple[list[PayoutRow], int, Decimal]:
        where, params = self._payment_where("p", "manager_user_id", "paid_on", company_id, filters)
        return self._paged(
            self._PAYOUT_SELECT,
            "FROM manager_payouts p",
            where,
            params,
            "p.paid_on DESC, p.created_at DESC",
            filters,
            PayoutRow,
        )

    def list_payouts_for(self, company_id: UUID, manager_id: UUID) -> list[PayoutRow]:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                self._PAYOUT_SELECT
                + "WHERE p.company_id=%s AND p.manager_user_id=%s ORDER BY p.paid_on DESC",
                (company_id, manager_id),
            )
            return [PayoutRow(*row) for row in cursor.fetchall()]

    def get_payout(self, company_id: UUID, payout_id: UUID) -> PayoutRow | None:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                self._PAYOUT_SELECT + "WHERE p.company_id=%s AND p.id=%s",
                (company_id, payout_id),
            )
            row = cursor.fetchone()
            return PayoutRow(*row) if row else None

    def create_payout(self, company_id: UUID, actor_id: UUID, values: dict[str, Any]) -> UUID:
        payout_id = uuid4()
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            currency = self._currency(cursor, company_id)
            cursor.execute(
                "INSERT INTO manager_payouts(id,company_id,manager_user_id,amount,currency,paid_on,"
                "method,reference,note,created_by_id,created_at,updated_at) VALUES(%s,%s,%s,%s,%s,"
                '%s,%s::"PaymentMethod",%s,%s,%s,NOW(),NOW())',
                (
                    payout_id,
                    company_id,
                    values["manager_user_id"],
                    values["amount"],
                    currency,
                    values["paid_on"],
                    values["method"],
                    values["reference"],
                    values["note"],
                    actor_id,
                ),
            )
            self._audit(
                cursor,
                actor_id,
                company_id,
                "MANAGER_PAYOUT_RECORDED",
                {"payout_id": str(payout_id), "amount": str(values["amount"])},
            )
        return payout_id

    # -- earnings ------------------------------------------------------------------------

    def manager_commission_tasks(
        self, company_id: UUID, manager_id: UUID
    ) -> list[CommissionTaskRow]:
        """Every non-cancelled task assigned to this manager, with its commission."""
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT t.id, t.number, t.title, s.name, t.status::text,
                    COALESCE(t.commission_final, 0), t.approved_at
                FROM tasks t JOIN company_services s ON s.id=t.service_id
                WHERE t.company_id=%s AND t.assignee_user_id=%s
                  AND t.assignee_type='MANAGER' AND t.status <> 'CANCELLED'
                ORDER BY t.approved_at DESC NULLS FIRST, t.created_at DESC
                """,
                (company_id, manager_id),
            )
            return [CommissionTaskRow(*row) for row in cursor.fetchall()]

    def manager_commission_in_range(
        self, company_id: UUID, manager_id: UUID, tz: str, start: date, end: date
    ) -> Decimal:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT COALESCE(SUM(commission_final),0) FROM tasks
                WHERE company_id=%(company)s AND assignee_user_id=%(manager)s
                  AND assignee_type='MANAGER' AND status IN {_BILLABLE}
                  AND {_range_sql(_local_date("approved_at"), start, end)}
                """,
                {
                    "company": company_id,
                    "manager": manager_id,
                    "tz": tz,
                    "start": start,
                    "end": end,
                },
            )
            return Decimal(_one(cursor)[0])

    def manager_payout_totals(self, company_id: UUID) -> dict[UUID, Decimal]:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT manager_user_id, SUM(amount) FROM manager_payouts WHERE company_id=%s "
                "GROUP BY manager_user_id",
                (company_id,),
            )
            return {row[0]: Decimal(row[1]) for row in cursor.fetchall()}

    def manager_earned_totals(self, company_id: UUID) -> dict[UUID, Decimal]:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                f"SELECT assignee_user_id, SUM(commission_final) FROM tasks WHERE company_id=%s "
                f"AND assignee_type='MANAGER' AND status IN {_BILLABLE} GROUP BY assignee_user_id",
                (company_id,),
            )
            return {row[0]: Decimal(row[1]) for row in cursor.fetchall()}

    # -- client summaries ----------------------------------------------------------------

    def client_service_counts(
        self,
        company_id: UUID,
        client_id: UUID | None,
        tz: str,
        start: date | None,
        end: date | None,
    ) -> list[ServiceCountRow]:
        """Per-service counts and money. Completed/charged use the approval date range;
        in-progress counts open work regardless of date."""
        approved_in_range = _range_sql(_local_date("t.approved_at"), start, end)
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT s.id, s.name, s.code,
                  COUNT(t.id) FILTER (WHERE t.status IN {_BILLABLE} AND {approved_in_range}),
                  COUNT(t.id) FILTER (WHERE t.status NOT IN {_CLOSED}),
                  COALESCE(SUM(t.client_price_final) FILTER (
                    WHERE t.status IN {_BILLABLE} AND {approved_in_range}), 0),
                  COALESCE(SUM(t.commission_final) FILTER (
                    WHERE t.status IN {_BILLABLE} AND {approved_in_range}), 0)
                FROM company_services s
                LEFT JOIN tasks t ON t.service_id = s.id AND t.company_id = s.company_id
                  AND (%(client)s::uuid IS NULL OR t.client_id = %(client)s::uuid)
                WHERE s.company_id = %(company)s
                GROUP BY s.id, s.name, s.code, s.sort_order
                HAVING COUNT(t.id) > 0 OR BOOL_OR(s.status = 'ACTIVE')
                ORDER BY s.sort_order, s.name
                """,
                {"company": company_id, "client": client_id, "tz": tz, "start": start, "end": end},
            )
            return [
                ServiceCountRow(
                    row[0],
                    row[1],
                    row[2],
                    int(row[3]),
                    int(row[4]),
                    Decimal(row[5]),
                    Decimal(row[6]),
                )
                for row in cursor.fetchall()
            ]

    def client_balances(
        self, company_id: UUID, tz: str, start: date | None, end: date | None
    ) -> list[ClientBalanceRow]:
        """Per-client work and money: counts/billing in range plus all-time balance."""
        created_in_range = _range_sql(_local_date("t.created_at"), start, end)
        approved_in_range = _range_sql(_local_date("t.approved_at"), start, end)
        received_in_range = _range_sql("p.received_on", start, end)
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT c.id, c.name, c.code,
                  COALESCE(work.total, 0), COALESCE(work.completed, 0), COALESCE(work.open, 0),
                  COALESCE(work.billed_range, 0), COALESCE(paid.received_range, 0),
                  COALESCE(work.billed_all, 0), COALESCE(paid.received_all, 0),
                  COALESCE(budget.total, 0)
                FROM clients c
                LEFT JOIN LATERAL (
                  SELECT
                    COUNT(*) FILTER (WHERE {created_in_range}) AS total,
                    COUNT(*) FILTER (WHERE t.status IN {_BILLABLE} AND {approved_in_range})
                      AS completed,
                    COUNT(*) FILTER (WHERE t.status NOT IN {_CLOSED}) AS open,
                    SUM(t.client_price_final) FILTER (
                      WHERE t.status IN {_BILLABLE} AND {approved_in_range}) AS billed_range,
                    SUM(t.client_price_final) FILTER (WHERE t.status IN {_BILLABLE}) AS billed_all
                  FROM tasks t WHERE t.client_id = c.id
                ) work ON TRUE
                LEFT JOIN LATERAL (
                  SELECT SUM(p.amount) FILTER (WHERE {received_in_range}) AS received_range,
                    SUM(p.amount) AS received_all
                  FROM client_payments p WHERE p.client_id = c.id
                ) paid ON TRUE
                LEFT JOIN LATERAL (
                  SELECT SUM(b.amount) AS total FROM client_budget_entries b
                  WHERE b.client_id = c.id
                ) budget ON TRUE
                WHERE c.company_id = %(company)s
                ORDER BY c.name
                """,
                {"company": company_id, "tz": tz, "start": start, "end": end},
            )
            return [
                ClientBalanceRow(
                    row[0],
                    row[1],
                    row[2],
                    int(row[3]),
                    int(row[4]),
                    int(row[5]),
                    Decimal(row[6]),
                    Decimal(row[7]),
                    Decimal(row[8]),
                    Decimal(row[9]),
                    Decimal(row[10]),
                )
                for row in cursor.fetchall()
            ]

    def client_month_charged(
        self, company_id: UUID, client_id: UUID, tz: str, start: date, end: date
    ) -> Decimal:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT COALESCE(SUM(client_price_final),0) FROM tasks
                WHERE company_id=%(company)s AND client_id=%(client)s AND status IN {_BILLABLE}
                  AND {_range_sql(_local_date("approved_at"), start, end)}
                """,
                {"company": company_id, "client": client_id, "tz": tz, "start": start, "end": end},
            )
            return Decimal(_one(cursor)[0])

    # -- team and company summaries ------------------------------------------------------

    def people_work(
        self, company_id: UUID, tz: str, start: date | None, end: date | None
    ) -> list[PersonWorkRow]:
        created_in_range = _range_sql(_local_date("t.created_at"), start, end)
        approved_in_range = _range_sql(_local_date("t.approved_at"), start, end)
        paid_in_range = _range_sql("p.paid_on", start, end)
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT u.id, u.name,
                  CASE r.code WHEN 'COMPANY_MANAGER' THEN 'MANAGER' ELSE 'EMPLOYEE' END,
                  COALESCE(work.total, 0), COALESCE(work.completed, 0), COALESCE(work.open, 0),
                  COALESCE(work.commission_range, 0), COALESCE(work.commission_all, 0),
                  COALESCE(payout.in_range, 0), COALESCE(payout.all_time, 0),
                  COALESCE(salary.in_range, 0), COALESCE(salary.all_time, 0)
                FROM users u
                JOIN roles r ON r.id = u.role_id
                LEFT JOIN LATERAL (
                  SELECT
                    COUNT(*) FILTER (WHERE t.status <> 'CANCELLED' AND {created_in_range})
                      AS total,
                    COUNT(*) FILTER (WHERE t.status IN {_BILLABLE} AND {approved_in_range})
                      AS completed,
                    COUNT(*) FILTER (WHERE t.status NOT IN {_CLOSED}) AS open,
                    SUM(t.commission_final) FILTER (
                      WHERE t.status IN {_BILLABLE} AND {approved_in_range}) AS commission_range,
                    SUM(t.commission_final) FILTER (WHERE t.status IN {_BILLABLE})
                      AS commission_all
                  FROM tasks t WHERE t.assignee_user_id = u.id AND t.company_id = u.company_id
                ) work ON TRUE
                LEFT JOIN LATERAL (
                  SELECT SUM(p.amount) FILTER (WHERE {paid_in_range}) AS in_range,
                    SUM(p.amount) AS all_time
                  FROM manager_payouts p WHERE p.manager_user_id = u.id
                ) payout ON TRUE
                LEFT JOIN LATERAL (
                  SELECT SUM(p.amount) FILTER (WHERE {paid_in_range}) AS in_range,
                    SUM(p.amount) AS all_time
                  FROM salary_payments p WHERE p.user_id = u.id
                ) salary ON TRUE
                WHERE u.company_id = %(company)s
                  AND r.code IN ('COMPANY_MANAGER', 'COMPANY_EMPLOYEE')
                ORDER BY u.name
                """,
                {"company": company_id, "tz": tz, "start": start, "end": end},
            )
            return [
                PersonWorkRow(
                    row[0],
                    row[1],
                    row[2],
                    int(row[3]),
                    int(row[4]),
                    int(row[5]),
                    Decimal(row[6]),
                    Decimal(row[7]),
                    Decimal(row[8]),
                    Decimal(row[9]),
                    Decimal(row[10]),
                    Decimal(row[11]),
                )
                for row in cursor.fetchall()
            ]

    def revenue_in_range(
        self, company_id: UUID, tz: str, start: date | None, end: date | None
    ) -> tuple[Decimal, Decimal, int]:
        """(revenue, manager commission, approved item count) for tasks approved in range."""
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT COALESCE(SUM(client_price_final),0), COALESCE(SUM(commission_final),0),
                  COUNT(*)
                FROM tasks
                WHERE company_id=%(company)s AND status IN {_BILLABLE}
                  AND {_range_sql(_local_date("approved_at"), start, end)}
                """,
                {"company": company_id, "tz": tz, "start": start, "end": end},
            )
            row = _one(cursor)
            return Decimal(row[0]), Decimal(row[1]), int(row[2])

    def task_counts(self, company_id: UUID, today: date) -> TaskCountsRow:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT
                  COUNT(*) FILTER (WHERE status NOT IN {_CLOSED}),
                  COUNT(*) FILTER (WHERE status = 'PENDING'),
                  COUNT(*) FILTER (WHERE status IN ('SUBMITTED','REVIEW')),
                  COUNT(*) FILTER (WHERE status NOT IN {_CLOSED} AND due_date < %s)
                FROM tasks WHERE company_id=%s
                """,
                (today, company_id),
            )
            row = _one(cursor)
            return TaskCountsRow(int(row[0]), int(row[1]), int(row[2]), int(row[3]))

    def worker_task_counts(self, company_id: UUID, user_id: UUID, today: date) -> dict[str, int]:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT
                  COUNT(*) FILTER (WHERE assignee_user_id=%(user)s AND status='ASSIGNED'),
                  COUNT(*) FILTER (WHERE assignee_user_id=%(user)s AND status='IN_PROGRESS'),
                  COUNT(*) FILTER (WHERE assignee_user_id=%(user)s AND status='SUBMITTED'),
                  COUNT(*) FILTER (WHERE assignee_user_id=%(user)s AND status='REVIEW'),
                  COUNT(*) FILTER (WHERE assignee_user_id=%(user)s AND status='APPROVED'),
                  COUNT(*) FILTER (WHERE assignee_user_id=%(user)s AND status='COMPLETED'),
                  COUNT(*) FILTER (WHERE assignee_user_id=%(user)s AND status NOT IN {_CLOSED}
                    AND due_date < %(today)s),
                  COUNT(*) FILTER (WHERE monitor_user_id=%(user)s AND status NOT IN {_CLOSED})
                FROM tasks WHERE company_id=%(company)s
                  AND (assignee_user_id=%(user)s OR monitor_user_id=%(user)s)
                """,
                {"company": company_id, "user": user_id, "today": today},
            )
            row = _one(cursor)
            keys = (
                "assigned",
                "in_progress",
                "submitted",
                "in_review",
                "approved",
                "completed",
                "overdue",
                "monitoring",
            )
            return {key: int(value) for key, value in zip(keys, row, strict=True)}

    def status_counts(self, company_id: UUID) -> dict[str, int]:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT status::text, COUNT(*) FROM tasks WHERE company_id=%s GROUP BY status",
                (company_id,),
            )
            return {str(row[0]): int(row[1]) for row in cursor.fetchall()}

    def attention_tasks(
        self, company_id: UUID, due_by: date, limit: int = 8
    ) -> list[AttentionTaskRow]:
        """Open tasks that are overdue or due on or before ``due_by``, soonest first."""
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT t.id, t.number, t.title, c.name, a.name, t.due_date, t.status::text
                FROM tasks t
                JOIN clients c ON c.id = t.client_id
                LEFT JOIN users a ON a.id = t.assignee_user_id
                WHERE t.company_id = %s AND t.status NOT IN {_CLOSED}
                  AND t.due_date IS NOT NULL AND t.due_date <= %s
                ORDER BY t.due_date ASC, t.number ASC
                LIMIT %s
                """,
                (company_id, due_by, limit),
            )
            return [AttentionTaskRow(*row) for row in cursor.fetchall()]

    def top_client_by_open_tasks(self, company_id: UUID) -> tuple[UUID, str, str, int] | None:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT c.id, c.name, c.code, COUNT(*) FROM tasks t JOIN clients c ON c.id=t.client_id
                WHERE t.company_id=%s AND t.status NOT IN {_CLOSED}
                GROUP BY c.id, c.name, c.code ORDER BY COUNT(*) DESC, c.name LIMIT 1
                """,
                (company_id,),
            )
            row = cursor.fetchone()
            return (row[0], row[1], row[2], int(row[3])) if row else None

    # -- helpers -------------------------------------------------------------------------

    @staticmethod
    def _payment_where(
        alias: str,
        subject_column: str,
        date_column: str,
        company_id: UUID,
        filters: PaymentListFilters,
    ) -> tuple[str, dict[str, Any]]:
        clauses = [f"{alias}.company_id = %(company)s"]
        params: dict[str, Any] = {"company": company_id}
        if filters.subject_id:
            clauses.append(f"{alias}.{subject_column} = %(subject)s")
            params["subject"] = filters.subject_id
        if filters.start:
            clauses.append(f"{alias}.{date_column} >= %(start)s")
            params["start"] = filters.start
        if filters.end:
            clauses.append(f"{alias}.{date_column} <= %(end)s")
            params["end"] = filters.end
        return " AND ".join(clauses), params

    @staticmethod
    def _paged(
        select_sql: str,
        from_sql: str,
        where: str,
        params: dict[str, Any],
        order: str,
        filters: PaymentListFilters,
        row_type: Any,
    ) -> tuple[list[Any], int, Decimal]:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                f"SELECT COUNT(*), COALESCE(SUM(p.amount),0) {from_sql} WHERE {where}", params
            )
            count_row = _one(cursor)
            cursor.execute(
                f"{select_sql} WHERE {where} ORDER BY {order} LIMIT %(limit)s OFFSET %(offset)s",
                {
                    **params,
                    "limit": filters.page_size,
                    "offset": (filters.page - 1) * filters.page_size,
                },
            )
            return (
                [row_type(*row) for row in cursor.fetchall()],
                int(count_row[0]),
                Decimal(count_row[1]),
            )
