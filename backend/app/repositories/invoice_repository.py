"""Client invoices (Phase 11). Lines and payments are snapshots taken when the invoice is made."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from app.database.connectivity import database_pool


@dataclass(frozen=True)
class InvoiceRow:
    id: UUID
    number: int
    status: str
    source: str
    client_id: UUID
    client_name: str
    client_code: str
    client_email: str | None
    client_address: str
    period_start: date
    period_end: date
    issue_date: date
    due_date: date | None
    currency: str
    subtotal: Decimal
    payments_total: Decimal
    budget_added: Decimal
    payments: list[dict[str, Any]]
    notes: str
    created_by_name: str
    sent_at: datetime | None
    paid_at: datetime | None
    created_at: datetime
    line_count: int

    @property
    def code(self) -> str:
        return f"INV-{self.number:04d}"


@dataclass(frozen=True)
class InvoiceLineRow:
    position: int
    task_id: UUID | None
    delivered_on: date
    title: str
    service_name: str
    amount: Decimal


@dataclass(frozen=True)
class CompanyProfile:
    name: str
    email: str | None
    phone: str | None
    address: str | None
    website: str | None


_SELECT = """
    SELECT i.id, i.number, i.status::text, i.source, i.client_id, c.name, c.code, c.email,
      CONCAT_WS(', ', NULLIF(c.address, ''), NULLIF(c.city, ''), NULLIF(c.state, ''),
                NULLIF(c.country, '')),
      i.period_start, i.period_end, i.issue_date, i.due_date, i.currency, i.subtotal,
      i.payments_total, i.budget_added, i.payments, i.notes, u.name, i.sent_at, i.paid_at,
      i.created_at,
      (SELECT COUNT(*) FROM invoice_lines l WHERE l.invoice_id = i.id)::int
    FROM invoices i
    JOIN clients c ON c.id = i.client_id
    JOIN users u ON u.id = i.created_by_id
"""


def _row(values: tuple[Any, ...]) -> InvoiceRow:
    return InvoiceRow(*values)


class InvoiceRepository:
    def create(
        self,
        company_id: UUID,
        client_id: UUID,
        actor_id: UUID,
        header: dict[str, Any],
        lines: list[dict[str, Any]],
    ) -> UUID:
        invoice_id = uuid4()
        with database_pool.connection(timeout=5) as connection, connection.cursor() as cursor:
            # Serialise numbering per company (same approach as task codes).
            cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"invoice:{company_id}",))
            cursor.execute(
                "SELECT COALESCE(MAX(number), 0) + 1 FROM invoices WHERE company_id=%s",
                (company_id,),
            )
            row = cursor.fetchone()
            number = int(row[0]) if row else 1
            cursor.execute(
                """
                INSERT INTO invoices (id, company_id, client_id, number, status, source,
                  period_start, period_end, issue_date, due_date, currency, subtotal,
                  payments_total, budget_added, payments, notes, created_by_id, created_at,
                  updated_at)
                VALUES (%s,%s,%s,%s,'DRAFT',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,
                  NOW() AT TIME ZONE 'UTC', NOW() AT TIME ZONE 'UTC')
                """,
                (
                    invoice_id,
                    company_id,
                    client_id,
                    number,
                    header["source"],
                    header["period_start"],
                    header["period_end"],
                    header["issue_date"],
                    header.get("due_date"),
                    header["currency"],
                    header["subtotal"],
                    header["payments_total"],
                    header["budget_added"],
                    json.dumps(header["payments"], default=str),
                    header.get("notes", ""),
                    actor_id,
                ),
            )
            for position, line in enumerate(lines, start=1):
                cursor.execute(
                    """
                    INSERT INTO invoice_lines (id, invoice_id, task_id, position, delivered_on,
                      title, service_name, amount)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        uuid4(),
                        invoice_id,
                        line.get("task_id"),
                        position,
                        line["delivered_on"],
                        str(line["title"])[:200],
                        str(line["service_name"])[:120],
                        line["amount"],
                    ),
                )
        return invoice_id

    def get(self, company_id: UUID, invoice_id: UUID) -> InvoiceRow | None:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(_SELECT + " WHERE i.company_id=%s AND i.id=%s", (company_id, invoice_id))
            row = cursor.fetchone()
            return _row(row) if row else None

    def lines(self, invoice_id: UUID) -> list[InvoiceLineRow]:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT position, task_id, delivered_on, title, service_name, amount "
                "FROM invoice_lines WHERE invoice_id=%s ORDER BY position",
                (invoice_id,),
            )
            return [InvoiceLineRow(*row) for row in cursor.fetchall()]

    def list(
        self,
        company_id: UUID,
        client_id: UUID | None,
        statuses: list[str] | None,
        page: int,
        page_size: int,
    ) -> tuple[list[InvoiceRow], int]:
        where = ["i.company_id=%(company)s"]
        params: dict[str, Any] = {
            "company": company_id,
            "limit": page_size,
            "offset": (page - 1) * page_size,
        }
        if client_id is not None:
            where.append("i.client_id=%(client)s")
            params["client"] = client_id
        if statuses:
            where.append("i.status::text = ANY(%(statuses)s)")
            params["statuses"] = statuses
        condition = " AND ".join(where)
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(f"SELECT COUNT(*) FROM invoices i WHERE {condition}", params)
            count = cursor.fetchone()
            cursor.execute(
                _SELECT
                + f" WHERE {condition} ORDER BY i.number DESC LIMIT %(limit)s OFFSET %(offset)s",
                params,
            )
            return [_row(row) for row in cursor.fetchall()], int(count[0]) if count else 0

    def find_auto(self, company_id: UUID, client_id: UUID, period_start: date) -> UUID | None:
        """An automatic (top-up) invoice already made for this budget period, if any."""
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM invoices WHERE company_id=%s AND client_id=%s AND source='TOP_UP' "
                "AND period_start=%s AND status <> 'VOID' LIMIT 1",
                (company_id, client_id, period_start),
            )
            row = cursor.fetchone()
            return row[0] if row else None

    def update(self, company_id: UUID, invoice_id: UUID, changes: dict[str, Any]) -> bool:
        allowed = {"status", "notes", "due_date", "sent_at", "paid_at"}
        fields = {key: value for key, value in changes.items() if key in allowed}
        if not fields:
            return True
        assignments = ", ".join(
            f'{key} = %({key})s::"InvoiceStatus"' if key == "status" else f"{key} = %({key})s"
            for key in fields
        )
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                f"UPDATE invoices SET {assignments}, updated_at = NOW() AT TIME ZONE 'UTC' "
                "WHERE company_id=%(company)s AND id=%(id)s",
                {**fields, "company": company_id, "id": invoice_id},
            )
            return bool(cursor.rowcount)

    def delete_draft(self, company_id: UUID, invoice_id: UUID) -> bool:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM invoices WHERE company_id=%s AND id=%s AND status='DRAFT'",
                (company_id, invoice_id),
            )
            return bool(cursor.rowcount)

    def company_profile(self, company_id: UUID) -> CompanyProfile:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT name, contact_email, phone, address, website FROM companies WHERE id=%s",
                (company_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return CompanyProfile("Adverse", None, None, None, None)
            return CompanyProfile(*row)

    def client_login_email(self, company_id: UUID, client_id: UUID) -> str | None:
        """The client's portal login email, falling back to the client record's email."""
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT COALESCE(u.email, c.email) FROM clients c LEFT JOIN users u ON u.id=c.user_id "
                "WHERE c.company_id=%s AND c.id=%s",
                (company_id, client_id),
            )
            row = cursor.fetchone()
            return row[0] if row else None
