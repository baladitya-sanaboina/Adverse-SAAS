import unittest
from datetime import UTC, datetime
from unittest.mock import patch
from uuid import UUID, uuid4

from app.repositories.organization_repository import (
    BranchRecord,
    DepartmentRecord,
    OrganizationConflict,
    OrganizationRepository,
)
from app.schemas.authentication import AuthContext
from app.schemas.organization import BranchCreate, DepartmentCreate, DepartmentUpdate
from app.services.authentication_service import AuthenticationError
from app.services.organization_service import OrganizationService


class FakeOrganizationRepository(OrganizationRepository):
    def __init__(self) -> None:
        self.departments: dict[tuple[UUID, UUID], DepartmentRecord] = {}
        self.branches: dict[tuple[UUID, UUID], BranchRecord] = {}
        self.last_company_id: UUID | None = None
        self.audits: list[str] = []

    def write_audit(
        self,
        action: str,
        actor_id: UUID,
        company_id: UUID,
        entity_type: str,
        entity_id: UUID,
        details: dict[str, object],
    ) -> None:
        self.audits.append(action)

    def list_departments(
        self, company_id: UUID, search: str, status: str | None
    ) -> tuple[DepartmentRecord, ...]:
        self.last_company_id = company_id
        return tuple(
            record
            for (tenant_id, _), record in self.departments.items()
            if tenant_id == company_id
            and (not search or search.lower() in record.name.lower())
            and (not status or record.status == status)
        )

    def get_department(self, company_id: UUID, item_id: UUID) -> DepartmentRecord | None:
        self.last_company_id = company_id
        return self.departments.get((company_id, item_id))

    def create_department(self, company_id: UUID, name: str, description: str) -> DepartmentRecord:
        if any(
            tenant_id == company_id and record.name.lower() == name.lower()
            for (tenant_id, _), record in self.departments.items()
        ):
            raise OrganizationConflict
        now = datetime.now(UTC)
        record = DepartmentRecord(uuid4(), name, description, "ACTIVE", now, now)
        self.departments[(company_id, record.id)] = record
        return record

    def update_department(
        self, company_id: UUID, item_id: UUID, values: dict[str, object]
    ) -> DepartmentRecord | None:
        previous = self.departments.get((company_id, item_id))
        if previous is None:
            return None
        record = DepartmentRecord(
            previous.id,
            str(values.get("name", previous.name)),
            str(values.get("description", previous.description)),
            str(values.get("status", previous.status)),
            previous.created_at,
            datetime.now(UTC),
        )
        self.departments[(company_id, item_id)] = record
        return record

    def list_branches(
        self, company_id: UUID, search: str, status: str | None
    ) -> tuple[BranchRecord, ...]:
        self.last_company_id = company_id
        return tuple(
            record for (tenant_id, _), record in self.branches.items() if tenant_id == company_id
        )

    def create_branch(self, company_id: UUID, values: dict[str, object]) -> BranchRecord:
        now = datetime.now(UTC)
        record = BranchRecord(
            uuid4(),
            str(values["name"]),
            str(values["code"]),
            str(values.get("address", "")),
            str(values.get("city", "")),
            str(values.get("state", "")),
            str(values.get("country", "")),
            "ACTIVE",
            now,
            now,
        )
        self.branches[(company_id, record.id)] = record
        return record


class OrganizationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = FakeOrganizationRepository()
        self.service = OrganizationService(self.repository)

    @staticmethod
    def context(company_id: UUID | None, role: str = "COMPANY_ADMIN") -> AuthContext:
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

    @patch("app.services.organization_service.validate_user_action_access", return_value=True)
    def test_company_can_only_list_its_own_departments(self, _: object) -> None:
        company_a, company_b = uuid4(), uuid4()
        self.service.create_department(
            self.context(company_a), DepartmentCreate(name="Engineering")
        )
        self.service.create_department(self.context(company_b), DepartmentCreate(name="Finance"))
        response = self.service.list_departments(self.context(company_a))
        self.assertEqual([item.name for item in response.items], ["Engineering"])
        self.assertEqual(self.repository.last_company_id, company_a)

    @patch("app.services.organization_service.validate_user_action_access", return_value=True)
    def test_cross_tenant_department_id_returns_not_found(self, _: object) -> None:
        company_a, company_b = uuid4(), uuid4()
        created = self.service.create_department(
            self.context(company_a), DepartmentCreate(name="Operations")
        )
        with self.assertRaisesRegex(AuthenticationError, "not found"):
            self.service.get_department(self.context(company_b), created.id)

    @patch("app.services.organization_service.validate_user_action_access", return_value=True)
    def test_duplicate_department_is_rejected(self, _: object) -> None:
        company_id = uuid4()
        self.service.create_department(self.context(company_id), DepartmentCreate(name="Sales"))
        with self.assertRaisesRegex(AuthenticationError, "already exists"):
            self.service.create_department(self.context(company_id), DepartmentCreate(name="sales"))

    @patch("app.services.organization_service.validate_user_action_access", return_value=True)
    def test_delete_soft_disables_department(self, _: object) -> None:
        context = self.context(uuid4())
        created = self.service.create_department(
            context, DepartmentCreate(name="People Operations")
        )
        disabled = self.service.disable_department(context, created.id)
        self.assertEqual(disabled.status, "INACTIVE")
        self.assertEqual(
            self.repository.audits,
            ["DEPARTMENT_CREATED", "DEPARTMENT_DEACTIVATED"],
        )

    @patch("app.services.organization_service.validate_user_action_access", return_value=True)
    def test_branch_code_is_normalized(self, _: object) -> None:
        response = self.service.create_branch(
            self.context(uuid4()), BranchCreate(name="Hyderabad", code="hyd-1")
        )
        self.assertEqual(response.code, "HYD-1")

    @patch("app.services.organization_service.validate_user_action_access", return_value=False)
    def test_missing_permission_is_forbidden(self, _: object) -> None:
        with self.assertRaisesRegex(AuthenticationError, "permission"):
            self.service.list_departments(self.context(uuid4()))

    @patch("app.services.organization_service.validate_user_action_access", return_value=True)
    def test_custom_company_role_with_permission_is_allowed(self, _: object) -> None:
        company_id = uuid4()
        response = self.service.list_departments(
            self.context(company_id, "COMPANY_EMPLOYEE__CUSTOM_MANAGER")
        )
        self.assertEqual(response.total, 0)
        self.assertEqual(self.repository.last_company_id, company_id)

    def test_company_context_is_required(self) -> None:
        with self.assertRaisesRegex(AuthenticationError, "Company access"):
            self.service.list_departments(self.context(None, "PLATFORM_OWNER"))

    def test_blank_and_tenant_fields_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            DepartmentCreate(name="  ")
        with self.assertRaises(ValueError):
            DepartmentCreate(name="Support", company_id=str(uuid4()))
        with self.assertRaises(ValueError):
            DepartmentUpdate(name=" ")


if __name__ == "__main__":
    unittest.main()
