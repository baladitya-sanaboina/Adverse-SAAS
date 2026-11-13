import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from uuid import UUID, uuid4

from pydantic import ValidationError

from app.repositories.employee_repository import (
    EmployeeConflict,
    EmployeeRecord,
    EmployeeReferenceError,
)
from app.schemas.authentication import AuthContext
from app.schemas.employee import EmployeeCreate, EmployeeListFilters, EmployeeUpdate
from app.services.authentication_service import AuthenticationError
from app.services.employee_service import EmployeeService


class FakeEmployeeRepository:
    def __init__(self) -> None:
        self.company_id = uuid4()
        self.other_company_id = uuid4()
        self.employee_id = uuid4()
        self.user_id = uuid4()
        self.department_id = uuid4()
        self.branch_id = uuid4()
        self.role_id = uuid4()
        self.conflict: str | None = None
        self.invalid_reference: str | None = None
        self.updated_values: dict[str, object] | None = None
        self.list_filters: EmployeeListFilters | None = None
        now = datetime.now(UTC)
        self.record = EmployeeRecord(
            self.employee_id,
            self.company_id,
            self.user_id,
            "Employee One",
            "employee@company.test",
            "Employee",
            "One",
            "+91 9876543210",
            "ACTIVE",
            "EMP-001",
            self.department_id,
            "Engineering",
            self.branch_id,
            "Hyderabad",
            self.role_id,
            "Company Employee",
            "COMPANY_EMPLOYEE",
            "ACTIVE",
            now,
            now,
        )

    def list(self, company_id: UUID, filters: EmployeeListFilters):
        self.list_filters = filters
        records = (self.record,) if company_id == self.company_id else ()
        return records, len(records)

    def get(self, company_id: UUID, employee_id: UUID):
        return (
            self.record
            if company_id == self.company_id and employee_id == self.employee_id
            else None
        )

    def create(
        self, company_id, actor_id, user_id, code, department_id, branch_id, role_id, status
    ):
        if self.conflict:
            raise EmployeeConflict(self.conflict)
        if self.invalid_reference:
            raise EmployeeReferenceError(self.invalid_reference)
        return self.record

    def update(self, company_id, actor_id, employee_id, values):
        if self.conflict:
            raise EmployeeConflict(self.conflict)
        if self.invalid_reference:
            raise EmployeeReferenceError(self.invalid_reference)
        self.updated_values = values
        return self.get(company_id, employee_id)

    def is_ready(self):
        return True


class EmployeeServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = FakeEmployeeRepository()
        self.service = EmployeeService(self.repository)  # type: ignore[arg-type]
        now = datetime.now(UTC)
        self.context = AuthContext(
            user_id=uuid4(),
            role="COMPANY_ADMIN",
            company_id=self.repository.company_id,
            user_type="company",
            session_id=uuid4(),
            issued_at=now,
            expires_at=now + timedelta(minutes=30),
        )
        self.request = EmployeeCreate(
            user_id=self.repository.user_id,
            employee_code="emp-001",
            department_id=self.repository.department_id,
            branch_id=self.repository.branch_id,
            role_id=self.repository.role_id,
            status="ACTIVE",
        )

    @patch("app.services.employee_service.validate_user_action_access", return_value=True)
    def test_create_list_get_and_update(self, _: object) -> None:
        created = self.service.create(self.context, self.request)
        self.assertEqual(created.employee_code, "EMP-001")
        listed = self.service.list(
            self.context, EmployeeListFilters(search="Employee", page=1, page_size=20)
        )
        self.assertEqual(listed.total, 1)
        self.assertEqual(listed.total_pages, 1)
        self.assertEqual(
            self.repository.list_filters,
            EmployeeListFilters(search="Employee", page=1, page_size=20),
        )
        self.assertEqual(
            self.service.get(self.context, self.repository.employee_id).company_id,
            self.repository.company_id,
        )
        self.service.update(
            self.context,
            self.repository.employee_id,
            EmployeeUpdate(status="INACTIVE", employee_code="emp-002", first_name="Updated"),
        )
        self.assertEqual(
            self.repository.updated_values,
            {
                "first_name": "Updated",
                "employee_code": "EMP-002",
                "status": "INACTIVE",
            },
        )

    @patch("app.services.employee_service.validate_user_action_access", return_value=True)
    def test_duplicate_user_and_code_are_conflicts(self, _: object) -> None:
        for field, code in (
            ("user", "EMPLOYEE_PROFILE_EXISTS"),
            ("employee_code", "EMPLOYEE_CODE_EXISTS"),
        ):
            self.repository.conflict = field
            with self.assertRaises(AuthenticationError) as raised:
                self.service.create(self.context, self.request)
            self.assertEqual(raised.exception.status_code, 409)
            self.assertEqual(raised.exception.code, code)

    @patch("app.services.employee_service.validate_user_action_access", return_value=True)
    def test_invalid_and_cross_tenant_relationships_are_rejected(self, _: object) -> None:
        for reference in ("user", "department", "branch", "role"):
            self.repository.invalid_reference = reference
            with self.assertRaises(AuthenticationError) as raised:
                self.service.create(self.context, self.request)
            self.assertEqual(raised.exception.status_code, 404)
            self.assertIn(reference.upper(), raised.exception.code)

    @patch("app.services.employee_service.validate_user_action_access", return_value=True)
    def test_cross_tenant_employee_is_not_found(self, _: object) -> None:
        foreign_context = self.context.model_copy(
            update={"company_id": self.repository.other_company_id}
        )
        with self.assertRaises(AuthenticationError) as raised:
            self.service.get(foreign_context, self.repository.employee_id)
        self.assertEqual(raised.exception.status_code, 404)

    @patch("app.services.employee_service.validate_user_action_access", return_value=False)
    def test_missing_permission_is_forbidden(self, _: object) -> None:
        with self.assertRaises(AuthenticationError) as raised:
            self.service.list(self.context, EmployeeListFilters())
        self.assertEqual(raised.exception.status_code, 403)

    @patch("app.services.employee_service.validate_user_action_access", return_value=True)
    def test_authorized_company_employee_can_view_directory(self, _: object) -> None:
        context = self.context.model_copy(update={"role": "COMPANY_EMPLOYEE"})
        self.assertEqual(self.service.list(context, EmployeeListFilters()).total, 1)

    def test_platform_role_is_forbidden(self) -> None:
        context = self.context.model_copy(
            update={"role": "PLATFORM_OWNER", "company_id": None, "user_type": "platform"}
        )
        with self.assertRaises(AuthenticationError) as raised:
            self.service.list(context, EmployeeListFilters())
        self.assertEqual(raised.exception.status_code, 403)

    @patch("app.services.employee_service.validate_user_action_access", return_value=True)
    def test_missing_employee_update_is_not_found(self, _: object) -> None:
        with self.assertRaises(AuthenticationError) as raised:
            self.service.update(self.context, uuid4(), EmployeeUpdate(status="ACTIVE"))
        self.assertEqual(raised.exception.status_code, 404)

    def test_schema_normalizes_code_and_rejects_invalid_payload(self) -> None:
        self.assertEqual(self.request.employee_code, "EMP-001")
        with self.assertRaises(ValidationError):
            EmployeeCreate(
                user_id=uuid4(),
                employee_code="bad code",
                department_id=uuid4(),
                branch_id=uuid4(),
                role_id=uuid4(),
            )
        with self.assertRaises(ValidationError):
            EmployeeUpdate()


if __name__ == "__main__":
    unittest.main()
