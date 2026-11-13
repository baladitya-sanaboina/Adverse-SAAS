from dataclasses import dataclass

from app.core.constants import CompanyStatus
from app.database.connectivity import database_pool


@dataclass(frozen=True)
class CompanyRecord:
    id: str
    name: str
    code: str
    subscription_plan: str
    status: str
    contact_email: str | None


class TenantRepository:
    def find_company(self, company_id: str) -> CompanyRecord | None:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id::text, name, code, subscription_plan, status::text, contact_email "
                    'FROM "companies" WHERE id = %s',
                    (company_id,),
                )
                record = cursor.fetchone()
                return CompanyRecord(*record) if record else None

    def get_company(self, company_id: str) -> CompanyRecord:
        company = self.find_company(company_id)
        if company is None:
            raise LookupError("Company not found.")
        return company

    def company_exists(self, company_id: str) -> bool:
        return self.find_company(company_id) is not None

    def foundation_is_ready(self) -> bool:
        try:
            with database_pool.connection(timeout=2) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT EXISTS (SELECT 1 FROM pg_tables "
                        "WHERE schemaname = 'public' AND tablename = 'companies')"
                    )
                    company_table_record = cursor.fetchone()
                    company_table_exists = bool(company_table_record and company_table_record[0])
                    cursor.execute(
                        "SELECT enumlabel FROM pg_enum "
                        "JOIN pg_type ON pg_type.oid = pg_enum.enumtypid "
                        "WHERE pg_type.typname = 'CompanyStatus'"
                    )
                    statuses = {row[0] for row in cursor.fetchall()}
                    return company_table_exists and statuses >= {
                        status.value for status in CompanyStatus
                    }
        except Exception:
            return False
