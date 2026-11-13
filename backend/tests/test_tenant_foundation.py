import unittest
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

from app.api.tenant import tenant_context
from app.repositories.tenant_repository import CompanyRecord
from app.schemas.authentication import AuthContext
from app.services.authentication_service import AuthenticationError
from app.services.tenant_service import (
    InvalidTenantIdentifier,
    TenantNotFound,
    TenantService,
    TenantUnavailable,
)

COMPANY_A_ID = "00000000-0000-0000-0000-000000000001"
COMPANY_B_ID = "00000000-0000-0000-0000-000000000002"


class FakeTenantRepository:
    def __init__(self):
        self.companies = {
            COMPANY_A_ID: CompanyRecord(COMPANY_A_ID, "Company A", "A", "Starter", "ACTIVE", None),
            COMPANY_B_ID: CompanyRecord(
                COMPANY_B_ID, "Company B", "B", "Starter", "SUSPENDED", None
            ),
        }

    def find_company(self, company_id: str):
        return self.companies.get(company_id)

    def foundation_is_ready(self) -> bool:
        return True


class TenantFoundationTests(unittest.TestCase):
    def setUp(self):
        self.service = TenantService(FakeTenantRepository())

    def test_active_company_context_loads(self):
        self.assertEqual(self.service.resolve_tenant(COMPANY_A_ID).code, "A")

    def test_suspended_company_is_denied(self):
        with self.assertRaises(TenantUnavailable):
            self.service.resolve_tenant(COMPANY_B_ID)

    def test_missing_company_is_denied(self):
        with self.assertRaises(TenantNotFound):
            self.service.resolve_tenant("00000000-0000-0000-0000-000000000003")

    def test_invalid_context_is_denied(self):
        with self.assertRaises(InvalidTenantIdentifier):
            self.service.resolve_tenant("not-a-uuid")

    def test_company_contexts_remain_distinct(self):
        company_a = self.service.get_current_company(COMPANY_A_ID)
        company_b = self.service.get_current_company(COMPANY_B_ID)
        self.assertNotEqual(company_a.id, company_b.id)

    def test_context_route_matches_authenticated_company(self):
        now = datetime.now(UTC)
        context = AuthContext(
            user_id=uuid4(),
            role="COMPANY_ADMIN",
            company_id=UUID(COMPANY_A_ID),
            user_type="company",
            session_id=uuid4(),
            issued_at=now,
            expires_at=now + timedelta(minutes=30),
        )
        request = SimpleNamespace(
            state=SimpleNamespace(tenant=self.service.resolve_tenant(COMPANY_A_ID))
        )
        response = tenant_context(request, context, COMPANY_A_ID)  # type: ignore[arg-type]
        self.assertEqual(response.id, COMPANY_A_ID)

        mismatch = context.model_copy(update={"company_id": UUID(COMPANY_B_ID)})
        with self.assertRaises(AuthenticationError) as denied:
            tenant_context(request, mismatch, COMPANY_A_ID)  # type: ignore[arg-type]
        self.assertEqual(denied.exception.code, "TENANT_CONTEXT_MISMATCH")


if __name__ == "__main__":
    unittest.main()
