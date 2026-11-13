import unittest
from datetime import UTC, datetime
from unittest.mock import patch
from uuid import uuid4

from app.repositories.company_dashboard_repository import (
    CompanyDashboardActivityRecord,
    CompanyDashboardRecord,
)
from app.schemas.authentication import AuthContext
from app.services.authentication_service import AuthenticationError
from app.services.company_dashboard_service import CompanyDashboardService


class FakeCompanyDashboardRepository:
    def __init__(self, company_id=None, employees=0, projects=0, clients=0):
        self.company_id = company_id or uuid4()
        self.employees = employees
        self.projects = projects
        self.clients = clients
        self.loaded_company_id = None

    def load(self, company_id, user_id):
        self.loaded_company_id = company_id
        if company_id != self.company_id:
            return None
        return CompanyDashboardRecord(
            company_id=company_id,
            company_name="Tenant Company",
            logo_url=None,
            user_id=user_id,
            user_name="Company Admin",
            employees=self.employees,
            projects=self.projects,
            clients=self.clients,
        )

    def load_recent_activity(self, company_id, limit=8):
        if company_id != self.company_id:
            return ()
        return (
            CompanyDashboardActivityRecord(
                action="USER_CREATED",
                subject="Employee One",
                description="Employee added to the company",
                occurred_at=datetime.now(UTC),
            ),
        )

    def is_ready(self):
        return True


class CompanyDashboardTests(unittest.TestCase):
    def context(self, company_id=None, role="COMPANY_ADMIN"):
        now = datetime.now(UTC)
        return AuthContext(
            user_id=uuid4(),
            role=role,
            company_id=company_id,
            user_type="company" if company_id else "platform",
            session_id=uuid4(),
            issued_at=now,
            expires_at=now,
        )

    @patch(
        "app.services.company_dashboard_service.validate_user_action_access",
        return_value=True,
    )
    def test_company_a_receives_only_company_a_counts(self, _):
        company_a = uuid4()
        repository = FakeCompanyDashboardRepository(company_a, employees=10, projects=4, clients=3)
        response = CompanyDashboardService(repository).get_dashboard(self.context(company_a))
        self.assertEqual(response.statistics.employees, 10)
        self.assertEqual(response.statistics.clients, 3)
        self.assertEqual(response.statistics.projects, 4)
        self.assertEqual(repository.loaded_company_id, company_a)

    @patch(
        "app.services.company_dashboard_service.validate_user_action_access",
        return_value=True,
    )
    def test_company_b_receives_only_company_b_counts(self, _):
        company_b = uuid4()
        repository = FakeCompanyDashboardRepository(company_b, employees=50, clients=7)
        response = CompanyDashboardService(repository).get_dashboard(self.context(company_b))
        self.assertEqual(response.statistics.employees, 50)
        self.assertEqual(repository.loaded_company_id, company_b)

    @patch(
        "app.services.company_dashboard_service.validate_user_action_access",
        return_value=True,
    )
    def test_company_cannot_select_another_tenant(self, _):
        company_a, company_b = uuid4(), uuid4()
        repository = FakeCompanyDashboardRepository(company_a, employees=10)
        with self.assertRaisesRegex(AuthenticationError, "not found"):
            CompanyDashboardService(repository).get_dashboard(self.context(company_b))

    def test_non_company_admin_is_denied(self):
        with self.assertRaisesRegex(AuthenticationError, "Company Admin"):
            CompanyDashboardService(FakeCompanyDashboardRepository()).get_dashboard(
                self.context(uuid4(), "COMPANY_EMPLOYEE")
            )

    def test_missing_company_context_is_denied(self):
        with self.assertRaisesRegex(AuthenticationError, "Company Admin"):
            CompanyDashboardService(FakeCompanyDashboardRepository()).get_dashboard(
                self.context(None)
            )

    @patch(
        "app.services.company_dashboard_service.validate_user_action_access",
        return_value=False,
    )
    def test_missing_dashboard_permission_is_denied(self, _):
        with self.assertRaisesRegex(AuthenticationError, "permission"):
            CompanyDashboardService(FakeCompanyDashboardRepository()).get_dashboard(
                self.context(uuid4())
            )

    @patch(
        "app.services.company_dashboard_service.validate_user_action_access",
        return_value=True,
    )
    def test_empty_company_returns_valid_empty_state(self, _):
        company_id = uuid4()
        response = CompanyDashboardService(
            FakeCompanyDashboardRepository(company_id)
        ).get_dashboard(self.context(company_id))
        self.assertEqual(response.statistics.employees, 0)
        self.assertEqual(response.statistics.clients, 0)
        self.assertEqual(response.statistics.projects, 0)
        self.assertIsNone(response.statistics.finance_total)


if __name__ == "__main__":
    unittest.main()
