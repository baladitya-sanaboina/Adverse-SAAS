import unittest
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.repositories.developer_management_repository import (
    DeveloperAuditRecord,
    DeveloperRecord,
    PermissionRecord,
)
from app.schemas.authentication import AuthContext
from app.schemas.developer_management import (
    DeveloperCreateRequest,
    DeveloperListFilters,
    DeveloperPermission,
    DeveloperStatusRequest,
    DeveloperUpdateRequest,
)
from app.services.authentication_service import AuthenticationError
from app.services.developer_management_service import DeveloperManagementService

OWNER_ID = UUID("11111111-1111-1111-1111-111111111111")


class FakeDeveloperRepository:
    def __init__(self):
        self.developer = None
        self.permissions = (PermissionRecord("COMPANIES", "VIEW"),)
        self.status_updates = []

    def actor_is_platform_owner(self, actor_id):
        return actor_id == OWNER_ID

    def email_exists(self, email, exclude_id=None):
        return self.developer is not None and self.developer.email == email

    def permission_catalog(self):
        return (PermissionRecord("COMPANIES", "VIEW"), PermissionRecord("DEVELOPERS", "EDIT"))

    def default_permissions(self):
        return self.permissions

    def permissions_for(self, developer_id):
        return self.permissions

    def audits_for(self, developer_id):
        return (DeveloperAuditRecord("DEVELOPER_CREATED", "Owner", None, datetime.now(UTC)),)

    def foundation_is_ready(self):
        return True

    def create_developer(self, **values):
        now = datetime.now(UTC)
        self.permissions = values["permissions"]
        self.developer = DeveloperRecord(
            uuid4(),
            values["first_name"],
            values["last_name"],
            f"{values['first_name']} {values['last_name']}",
            values["email"],
            values["phone"],
            values["status"],
            now,
            now,
            None,
        )
        return self.developer

    def list_developers(self, **filters):
        return ((self.developer,) if self.developer else (), 1 if self.developer else 0)

    def get_developer(self, developer_id):
        return self.developer if self.developer and self.developer.id == developer_id else None

    def update_developer(self, **values):
        if not self.developer:
            return None
        self.permissions = values["permissions"]
        self.developer = DeveloperRecord(
            self.developer.id,
            values["first_name"],
            values["last_name"],
            f"{values['first_name']} {values['last_name']}",
            self.developer.email,
            values["phone"],
            values["status"],
            self.developer.created_at,
            datetime.now(UTC),
            None,
        )
        return self.developer

    def update_status(self, **values):
        if not self.developer:
            return None
        self.status_updates.append(values["status"])
        self.developer = DeveloperRecord(**{**self.developer.__dict__, "status": values["status"]})
        return self.developer


class DeveloperManagementTests(unittest.TestCase):
    def setUp(self):
        self.repository = FakeDeveloperRepository()
        self.service = DeveloperManagementService(self.repository)
        now = datetime.now(UTC)
        self.context = AuthContext(
            user_id=OWNER_ID,
            role="PLATFORM_OWNER",
            company_id=None,
            user_type="platform",
            session_id=uuid4(),
            issued_at=now,
            expires_at=now,
        )

    def create_request(self, email="dev@example.com"):
        return DeveloperCreateRequest(
            first_name="Asha",
            last_name="Dev",
            email=email,
            phone="+91 98765 43210",
            password="StrongPass!123",
            confirm_password="StrongPass!123",
            status="ACTIVE",
            permissions=[DeveloperPermission(module="COMPANIES", action="VIEW")],
        )

    def test_create_and_duplicate_validation(self):
        created = self.service.create(self.context, self.create_request())
        self.assertEqual(created.name, "Asha Dev")
        self.assertEqual(created.permissions[0].module, "COMPANIES")
        with self.assertRaisesRegex(AuthenticationError, "already registered"):
            self.service.create(self.context, self.create_request())

    def test_list_search_filter_sort_and_pagination_response(self):
        self.service.create(self.context, self.create_request())
        result = self.service.list(
            self.context,
            DeveloperListFilters(search="asha", status="ACTIVE", sort="a-z", page=1, page_size=10),
        )
        self.assertEqual(result.total, 1)
        self.assertEqual(result.total_pages, 1)

    def test_update_permissions_and_deactivate(self):
        created = self.service.create(self.context, self.create_request())
        updated = self.service.update(
            self.context,
            created.id,
            DeveloperUpdateRequest(
                first_name="Asha",
                last_name="Updated",
                phone="+91 90000 00000",
                status="ACTIVE",
                permissions=[DeveloperPermission(module="DEVELOPERS", action="EDIT")],
            ),
        )
        self.assertEqual(updated.last_name, "Updated")
        inactive = self.service.update_status(
            self.context, created.id, DeveloperStatusRequest(status="INACTIVE")
        )
        self.assertEqual(inactive.status, "INACTIVE")

    def test_non_platform_owner_and_invalid_permission_rejected(self):
        invalid = self.context.model_copy(update={"role": "DEVELOPER"})
        with self.assertRaises(AuthenticationError):
            self.service.list(invalid, DeveloperListFilters())
        request = self.create_request()
        request.permissions = [DeveloperPermission(module="UNKNOWN", action="VIEW")]
        with self.assertRaisesRegex(AuthenticationError, "Unknown permission"):
            self.service.create(self.context, request)


if __name__ == "__main__":
    unittest.main()
