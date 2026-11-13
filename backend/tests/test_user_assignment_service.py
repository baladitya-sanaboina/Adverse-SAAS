import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.repositories.user_assignment_repository import CompanyUserRecord
from app.schemas.authentication import AuthContext
from app.schemas.user_assignments import UserAssignmentUpdate
from app.services.authentication_service import AuthenticationError
from app.services.user_assignment_service import UserAssignmentService


class UserAssignmentServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.company_id, self.actor_id, self.user_id = uuid4(), uuid4(), uuid4()
        now = datetime.now(UTC)
        self.context = AuthContext(
            user_id=self.actor_id,
            role="COMPANY_ADMIN",
            company_id=self.company_id,
            user_type="company",
            session_id=uuid4(),
            issued_at=now,
            expires_at=now + timedelta(minutes=30),
        )
        self.record = CompanyUserRecord(
            self.user_id,
            "Employee",
            "employee@example.com",
            "ACTIVE",
            uuid4(),
            "Company Employee",
            "COMPANY_EMPLOYEE",
            uuid4(),
            "Engineering",
            uuid4(),
            "Hyderabad",
        )
        self.repository = MagicMock()
        self.repository.list_users.return_value = (self.record,)
        self.repository.options.return_value = (
            [(self.record.role_id, self.record.role_name)],
            [(self.record.department_id, "Engineering")],
            [(self.record.branch_id, "Hyderabad")],
        )
        self.repository.assign.return_value = self.record
        self.service = UserAssignmentService(self.repository)

    @patch("app.services.user_assignment_service.validate_user_action_access", return_value=True)
    def test_lists_only_repository_tenant_users(self, _: MagicMock) -> None:
        response = self.service.list_users(self.context)
        self.repository.list_users.assert_called_once_with(self.company_id)
        self.assertEqual(response.items[0].email, self.record.email)

    @patch("app.services.user_assignment_service.validate_user_action_access", return_value=True)
    def test_assignment_is_combined_and_tenant_bound(self, _: MagicMock) -> None:
        request = UserAssignmentUpdate(
            role_id=self.record.role_id,
            department_id=self.record.department_id,
            branch_id=self.record.branch_id,
        )
        self.service.assign(self.context, self.user_id, request)
        self.repository.assign.assert_called_once_with(
            self.company_id,
            self.user_id,
            self.actor_id,
            request.role_id,
            request.department_id,
            request.branch_id,
        )

    @patch("app.services.user_assignment_service.validate_user_action_access", return_value=True)
    def test_cross_tenant_or_missing_option_is_not_found(self, _: MagicMock) -> None:
        self.repository.assign.return_value = None
        with self.assertRaises(AuthenticationError) as raised:
            self.service.assign(self.context, self.user_id, UserAssignmentUpdate(role_id=uuid4()))
        self.assertEqual(raised.exception.status_code, 404)

    @patch("app.services.user_assignment_service.validate_user_action_access", return_value=True)
    def test_company_admin_cannot_change_own_assignment(self, _: MagicMock) -> None:
        with self.assertRaises(AuthenticationError) as raised:
            self.service.assign(
                self.context,
                self.actor_id,
                UserAssignmentUpdate(role_id=self.record.role_id),
            )
        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(raised.exception.code, "SELF_ASSIGNMENT_NOT_ALLOWED")
        self.repository.assign.assert_not_called()

    def test_employee_is_forbidden(self) -> None:
        context = self.context.model_copy(update={"role": "COMPANY_EMPLOYEE"})
        with self.assertRaises(AuthenticationError) as raised:
            self.service.list_users(context)
        self.assertEqual(raised.exception.status_code, 403)

    @patch("app.services.user_assignment_service.validate_user_action_access", return_value=False)
    def test_missing_permission_is_forbidden(self, _: MagicMock) -> None:
        with self.assertRaises(AuthenticationError) as raised:
            self.service.options(self.context)
        self.assertEqual(raised.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
