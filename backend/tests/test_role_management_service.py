import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from uuid import UUID, uuid4

from app.repositories.role_management_repository import RoleAssigned, RoleConflict, RoleRecord
from app.schemas.authentication import AuthContext
from app.schemas.role_management import RoleCreate, RoleUpdate
from app.services.authentication_service import AuthenticationError
from app.services.role_management_service import RoleManagementService


class FakeRoleRepository:
    def __init__(self) -> None:
        self.company_id = uuid4()
        self.role_id = uuid4()
        now = datetime.now(UTC)
        self.record = RoleRecord(
            self.role_id,
            "Project Manager",
            "COMPANY_EMPLOYEE__TEST_PROJECT_MANAGER",
            "Project delivery access",
            "ACTIVE",
            False,
            0,
            1,
            now,
            now,
        )
        self.permissions = ["PROJECTS.VIEW"]
        self.conflict = False
        self.assigned = False

    def list_roles(self, company_id: UUID, search: str, status: str | None):
        return (self.record,) if company_id == self.company_id else ()

    def get_role(self, company_id: UUID, role_id: UUID):
        return (
            (self.record, self.permissions)
            if company_id == self.company_id and role_id == self.role_id
            else None
        )

    def permission_catalog(self):
        return (("PROJECTS", "Projects", "VIEW", "View"), ("PROJECTS", "Projects", "EDIT", "Edit"))

    def valid_permission_keys(self):
        return {"PROJECTS.VIEW", "PROJECTS.EDIT"}

    def create(self, company_id, actor_id, name, description, permissions):
        if self.conflict:
            raise RoleConflict
        self.permissions = permissions
        return self.role_id

    def update(self, company_id, actor_id, role_id, values):
        if self.conflict:
            raise RoleConflict
        self.permissions = values.get("permissions", self.permissions)
        return company_id == self.company_id and role_id == self.role_id

    def delete(self, company_id, actor_id, role_id):
        if self.assigned:
            raise RoleAssigned
        return company_id == self.company_id and role_id == self.role_id

    def is_ready(self):
        return True


class RoleManagementServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        now = datetime.now(UTC)
        self.repository = FakeRoleRepository()
        self.service = RoleManagementService(self.repository)
        self.context = AuthContext(
            user_id=uuid4(),
            role="COMPANY_ADMIN",
            company_id=self.repository.company_id,
            user_type="company",
            session_id=uuid4(),
            issued_at=now,
            expires_at=now + timedelta(minutes=30),
        )

    @patch("app.services.role_management_service.validate_user_action_access", return_value=True)
    def test_create_and_permission_catalog(self, _: object) -> None:
        created = self.service.create(
            self.context,
            RoleCreate(name="Project Manager", permissions=["PROJECTS.VIEW"]),
        )
        self.assertEqual(created.id, self.repository.role_id)
        self.assertEqual(self.service.permission_catalog(self.context).modules[0].code, "PROJECTS")

    @patch("app.services.role_management_service.validate_user_action_access", return_value=True)
    def test_update_permissions_and_safe_delete(self, _: object) -> None:
        updated = self.service.update(
            self.context,
            self.repository.role_id,
            RoleUpdate(permissions=["PROJECTS.VIEW", "PROJECTS.EDIT"]),
        )
        self.assertEqual(updated.permissions, ["PROJECTS.VIEW", "PROJECTS.EDIT"])
        self.repository.assigned = True
        with self.assertRaises(AuthenticationError) as raised:
            self.service.delete(self.context, self.repository.role_id)
        self.assertEqual(raised.exception.status_code, 409)

    @patch("app.services.role_management_service.validate_user_action_access", return_value=True)
    def test_invalid_permission_and_cross_tenant_role_are_rejected(self, _: object) -> None:
        with self.assertRaises(AuthenticationError) as invalid:
            self.service.create(
                self.context, RoleCreate(name="Manager", permissions=["UNKNOWN.VIEW"])
            )
        self.assertEqual(invalid.exception.status_code, 422)
        with self.assertRaises(AuthenticationError) as missing:
            self.service.get_role(self.context, uuid4())
        self.assertEqual(missing.exception.status_code, 404)

    @patch("app.services.role_management_service.validate_user_action_access", return_value=True)
    def test_duplicate_role_name_is_conflict(self, _: object) -> None:
        self.repository.conflict = True
        with self.assertRaises(AuthenticationError) as raised:
            self.service.create(self.context, RoleCreate(name="Project Manager"))
        self.assertEqual(raised.exception.status_code, 409)

    def test_employee_is_forbidden(self) -> None:
        employee = self.context.model_copy(update={"role": "COMPANY_EMPLOYEE"})
        with self.assertRaises(AuthenticationError) as raised:
            self.service.list_roles(employee, "", None)
        self.assertEqual(raised.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
