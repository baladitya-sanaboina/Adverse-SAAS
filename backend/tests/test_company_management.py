import unittest
from datetime import UTC, datetime
from unittest.mock import patch
from uuid import uuid4

from app.repositories.company_management_repository import CompanyAuditRecord, CompanyRecord
from app.schemas.authentication import AuthContext
from app.schemas.company_management import CompanyListFilters, CompanyStatusRequest
from app.services.company_management_service import CompanyManagementService


class FakeCompanyRepository:
    def __init__(self):
        now = datetime.now(UTC)
        self.record = CompanyRecord(
            uuid4(),
            "Acme",
            "ACME",
            "admin@acme.test",
            "Starter",
            "ACTIVE",
            now,
            now,
            uuid4(),
            "Acme Admin",
            "admin@acme.test",
            "ACTIVE",
            3,
            2,
            1,
        )
        self.views = 0

    def list_companies(self, filters):
        return ((self.record,), 1)

    def summary(self):
        return (1, 1, 0, 0, 0)

    def get_company(self, company_id):
        return self.record if company_id == self.record.id else None

    def audits_for(self, company_id):
        return (CompanyAuditRecord("COMPANY_VIEWED", "Owner", None, None, datetime.now(UTC)),)

    def subscription_for(self, company_id):
        return {
            "plan_id": None,
            "plan_name": self.record.subscription_plan,
            "plan_code": None,
            "status": "UNASSIGNED",
            "activation_date": None,
            "expiration_date": None,
            "features": {},
            "limits": {},
        }

    def record_view(self, actor_id, company_id):
        self.views += 1

    def update_status(self, actor_id, company_id, status):
        if company_id != self.record.id:
            return None
        self.record = CompanyRecord(**{**self.record.__dict__, "status": status})
        return self.record

    def is_ready(self):
        return True


class CompanyManagementTests(unittest.TestCase):
    def setUp(self):
        self.repository = FakeCompanyRepository()
        self.service = CompanyManagementService(self.repository)
        now = datetime.now(UTC)
        self.context = AuthContext(
            user_id=uuid4(),
            role="PLATFORM_OWNER",
            company_id=None,
            user_type="platform",
            session_id=uuid4(),
            issued_at=now,
            expires_at=now,
        )

    @patch("app.services.company_management_service.validate_user_action_access", return_value=True)
    def test_list_detail_and_status(self, _permission):
        result = self.service.list(
            self.context,
            CompanyListFilters(search="acme", status="ACTIVE", plan="Starter", sort="a-z"),
        )
        self.assertEqual(result.total, 1)
        detail = self.service.get(self.context, self.repository.record.id)
        self.assertEqual(detail.company_admin.email, "admin@acme.test")
        self.assertEqual(self.repository.views, 1)
        for status in ("PENDING", "INACTIVE", "SUSPENDED", "ACTIVE"):
            updated = self.service.update_status(
                self.context, self.repository.record.id, CompanyStatusRequest(status=status)
            )
            self.assertEqual(updated.status, status)

    @patch(
        "app.services.company_management_service.validate_user_action_access", return_value=False
    )
    def test_permission_is_required(self, _permission):
        with self.assertRaisesRegex(Exception, "VIEW access"):
            self.service.list(self.context, CompanyListFilters())


if __name__ == "__main__":
    unittest.main()
