import unittest
from datetime import UTC, datetime
from uuid import uuid4

from app.repositories.current_user_repository import (
    CurrentUserPermissionRecord,
    CurrentUserRecord,
)
from app.schemas.authentication import AuthContext
from app.services.authentication_service import AuthenticationError
from app.services.current_user_service import CurrentUserService


class FakeCurrentUserRepository:
    def __init__(self, record: CurrentUserRecord):
        self.record = record

    def load_profile(self, user_id):
        return self.record if user_id == self.record.id else None

    def load_permissions(self, role_id, user_id=None):
        if role_id != self.record.role_id:
            return ()
        return (CurrentUserPermissionRecord("PROJECTS", "Projects", "VIEW", "View"),)

    def foundation_is_ready(self):
        return True


def context_for(record: CurrentUserRecord) -> AuthContext:
    now = datetime.now(UTC)
    return AuthContext(
        user_id=record.id,
        role=record.role_code,
        company_id=record.company_id,
        user_type="company" if record.company_id else "platform",
        session_id=uuid4(),
        issued_at=now,
        expires_at=now,
    )


class CurrentUserServiceTests(unittest.TestCase):
    def company_user(self, *, user_status="ACTIVE", company_status="ACTIVE"):
        return CurrentUserRecord(
            id=uuid4(),
            name="Current User",
            email="current@example.com",
            status=user_status,
            created_at=datetime.now(UTC),
            company_id=uuid4(),
            company_name="Example Company",
            company_code="EXAMPLE",
            subscription_plan="Starter",
            company_status=company_status,
            subscription_features={"PROJECTS": True, "CRM": False},
            role_id=uuid4(),
            role_name="Company Employee",
            role_code="COMPANY_EMPLOYEE",
        )

    def test_returns_safe_profile_company_role_and_permissions(self):
        record = self.company_user()
        response = CurrentUserService(FakeCurrentUserRepository(record)).get_current_user(
            context_for(record)
        )
        self.assertEqual(response.user.email, record.email)
        self.assertEqual(response.company.code, "EXAMPLE")
        self.assertTrue(response.company.subscription_features["PROJECTS"])
        self.assertEqual(response.role.code, "COMPANY_EMPLOYEE")
        self.assertEqual(response.permissions[0].module, "PROJECTS")
        self.assertEqual(response.permissions[0].action, "VIEW")
        self.assertNotIn("password", response.model_dump())

    def test_platform_user_has_no_company(self):
        record = self.company_user()
        record = CurrentUserRecord(
            **{
                **record.__dict__,
                "company_id": None,
                "company_name": None,
                "company_code": None,
                "subscription_plan": None,
                "company_status": None,
                "role_name": "Platform Owner",
                "role_code": "PLATFORM_OWNER",
            }
        )
        response = CurrentUserService(FakeCurrentUserRepository(record)).get_current_user(
            context_for(record)
        )
        self.assertIsNone(response.company)

    def test_inactive_user_and_company_are_rejected(self):
        inactive_user = self.company_user(user_status="SUSPENDED")
        with self.assertRaises(AuthenticationError):
            CurrentUserService(FakeCurrentUserRepository(inactive_user)).get_current_user(
                context_for(inactive_user)
            )
        inactive_company = self.company_user(company_status="SUSPENDED")
        with self.assertRaises(AuthenticationError):
            CurrentUserService(FakeCurrentUserRepository(inactive_company)).get_current_user(
                context_for(inactive_company)
            )


if __name__ == "__main__":
    unittest.main()
