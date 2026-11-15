"""Monthly packages and per-client GST (owner requests 2026-11-15).

A package charges its monthly price once a month, from its start date until it ends; the first
month is charged on the start date, later months on the 1st. The charges are worked out in SQL
(``package_charges_sql``) so every money total (billing, sheets, budgets, revenue, invoices)
includes them without a scheduled job. Videos covered by a package are approved at price 0 and
carry the package id; extra videos keep the client's per-item price.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from app.database.connectivity import database_pool

# Today in the company's own timezone (the package rows know their company).
_TODAY = (
    "(now() AT TIME ZONE COALESCE((SELECT NULLIF(d.timezone, '') FROM company_tenant_defaults d "
    "WHERE d.company_id = p.company_id), 'UTC'))::date"
)


def package_charges_sql() -> str:
    """A subquery of every package charge so far for %(company)s:
    (client_id, package_id, name, amount, charge_on)."""
    return f"""(
      SELECT x.client_id, x.package_id, x.name, x.amount, x.charge_on FROM (
        SELECT p.client_id, p.id AS package_id, p.name, p.monthly_price AS amount,
          GREATEST(p.starts_on, m.month::date) AS charge_on,
          LEAST(COALESCE(p.ends_on, 'infinity'::date), {_TODAY}) AS last_day
        FROM client_packages p
        CROSS JOIN LATERAL generate_series(
          date_trunc('month', p.starts_on), {_TODAY}::timestamp, interval '1 month'
        ) AS m(month)
        WHERE p.company_id = %(company)s
      ) x
      WHERE x.charge_on <= x.last_day
    )"""


@dataclass(frozen=True)
class PackageRow:
    id: UUID
    client_id: UUID
    name: str
    monthly_price: Decimal
    videos_included: int
    starts_on: date
    ends_on: date | None
    created_by_name: str
    created_at: datetime


@dataclass(frozen=True)
class ClientTaxRow:
    gst_enabled: bool
    gst_rate: Decimal
    gstin: str


_PACKAGE_SELECT = """
    SELECT p.id, p.client_id, p.name, p.monthly_price, p.videos_included, p.starts_on, p.ends_on,
      u.name, p.created_at
    FROM client_packages p JOIN users u ON u.id = p.created_by_id
"""


class PackageRepository:
    def list(self, company_id: UUID, client_id: UUID) -> list[PackageRow]:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                _PACKAGE_SELECT + " WHERE p.company_id=%s AND p.client_id=%s "
                "ORDER BY p.starts_on DESC, p.created_at DESC",
                (company_id, client_id),
            )
            return [PackageRow(*row) for row in cursor.fetchall()]

    def get(self, company_id: UUID, package_id: UUID) -> PackageRow | None:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                _PACKAGE_SELECT + " WHERE p.company_id=%s AND p.id=%s", (company_id, package_id)
            )
            row = cursor.fetchone()
            return PackageRow(*row) if row else None

    def active_on(self, company_id: UUID, client_id: UUID, day: date) -> PackageRow | None:
        """The package that covers this day, if any (the latest one to start)."""
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                _PACKAGE_SELECT + " WHERE p.company_id=%s AND p.client_id=%s AND p.starts_on <= %s"
                " AND (p.ends_on IS NULL OR p.ends_on >= %s)"
                " ORDER BY p.starts_on DESC, p.created_at DESC LIMIT 1",
                (company_id, client_id, day, day),
            )
            row = cursor.fetchone()
            return PackageRow(*row) if row else None

    def covered_in_month(
        self, package_id: UUID, tz: str, month_start: date, month_end: date
    ) -> int:
        """Videos this package already covered in a month (by approval date)."""
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM tasks WHERE package_id=%s "
                "AND status IN ('APPROVED','COMPLETED') "
                "AND (approved_at AT TIME ZONE 'UTC' AT TIME ZONE %s)::date BETWEEN %s AND %s",
                (package_id, tz, month_start, month_end),
            )
            row = cursor.fetchone()
            return int(row[0]) if row else 0

    def running_after(self, company_id: UUID, client_id: UUID, day: date) -> PackageRow | None:
        """A package still running on or after this day (it must be ended first)."""
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                _PACKAGE_SELECT + " WHERE p.company_id=%s AND p.client_id=%s "
                "AND (p.ends_on IS NULL OR p.ends_on >= %s) LIMIT 1",
                (company_id, client_id, day),
            )
            row = cursor.fetchone()
            return PackageRow(*row) if row else None

    def create(
        self,
        company_id: UUID,
        client_id: UUID,
        actor_id: UUID,
        name: str,
        monthly_price: Decimal,
        videos_included: int,
        starts_on: date,
    ) -> UUID:
        package_id = uuid4()
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO client_packages (id, company_id, client_id, name, monthly_price, "
                "videos_included, starts_on, created_by_id, created_at, updated_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,NOW(),NOW())",
                (
                    package_id,
                    company_id,
                    client_id,
                    name,
                    monthly_price,
                    videos_included,
                    starts_on,
                    actor_id,
                ),
            )
        return package_id

    def end(self, company_id: UUID, package_id: UUID, ends_on: date) -> bool:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "UPDATE client_packages SET ends_on=%s, updated_at=NOW() "
                "WHERE company_id=%s AND id=%s AND starts_on <= %s",
                (ends_on, company_id, package_id, ends_on),
            )
            return cursor.rowcount == 1

    def remove_unstarted(self, company_id: UUID, package_id: UUID) -> bool:
        """Remove a package that has not started and covered nothing yet (a mistake)."""
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM client_packages p WHERE p.company_id=%s AND p.id=%s "
                f"AND p.starts_on > {_TODAY} "
                "AND NOT EXISTS (SELECT 1 FROM tasks t WHERE t.package_id = p.id)",
                (company_id, package_id),
            )
            return cursor.rowcount == 1

    # -- GST per client -------------------------------------------------------------------

    def client_tax(self, company_id: UUID, client_id: UUID) -> ClientTaxRow | None:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT gst_enabled, gst_rate, gstin FROM clients WHERE company_id=%s AND id=%s",
                (company_id, client_id),
            )
            row = cursor.fetchone()
            return ClientTaxRow(bool(row[0]), Decimal(row[1]), str(row[2])) if row else None

    def set_client_tax(
        self, company_id: UUID, client_id: UUID, enabled: bool, rate: Decimal, gstin: str
    ) -> bool:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                "UPDATE clients SET gst_enabled=%s, gst_rate=%s, gstin=%s, updated_at=NOW() "
                "WHERE company_id=%s AND id=%s",
                (enabled, rate, gstin, company_id, client_id),
            )
            return cursor.rowcount == 1
