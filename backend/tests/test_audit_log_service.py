import unittest
from datetime import UTC, datetime
from uuid import uuid4

from app.repositories.audit_log_repository import AuditLogRecord
from app.schemas.audit_logs import AuditLogFilters
from app.schemas.authentication import AuthContext
from app.services.audit_log_service import AuditLogService


class FakeAuditLogRepository:
    def __init__(self):
        self.record = AuditLogRecord(
            id=uuid4(),
            category="COMPANY",
            action="COMPANY_ACTIVATED",
            actor_id=uuid4(),
            actor_name="Adverse Admin",
            actor_email="admin@loopless.in",
            company_id=uuid4(),
            company_name="Example Company",
            target="Example Company",
            details="SUSPENDED → ACTIVE",
            created_at=datetime.now(UTC),
        )

    def actor_is_platform_owner(self, actor_id):
        return True

    def list_logs(self, filters):
        return ((self.record,), 1)

    def summary(self):
        return {"COMPANY": 1}

    def is_ready(self):
        return True


class AuditLogServiceTests(unittest.TestCase):
    def setUp(self):
        now = datetime.now(UTC)
        self.repository = FakeAuditLogRepository()
        self.service = AuditLogService(self.repository)
        self.owner = AuthContext(
            user_id=uuid4(),
            role="PLATFORM_OWNER",
            company_id=None,
            user_type="platform",
            session_id=uuid4(),
            issued_at=now,
            expires_at=now,
        )

    def test_platform_owner_receives_paginated_audit_activity(self):
        response = self.service.list(self.owner, AuditLogFilters())
        self.assertEqual(response.total, 1)
        self.assertEqual(response.items[0].action, "COMPANY_ACTIVATED")
        self.assertEqual(response.summary.categories, {"COMPANY": 1})
        self.assertEqual(response.items[0].created_at.utcoffset(), UTC.utcoffset(None))

    def test_new_audit_categories_are_serialized(self):
        for category in (
            "ORGANIZATION",
            "INVITATION",
            "PROFILE",
            "AUTHENTICATION",
            "EMPLOYEE",
            "CRM",
        ):
            with self.subTest(category=category):
                self.repository.record = AuditLogRecord(
                    **{**self.repository.record.__dict__, "category": category}
                )
                response = self.service.list(self.owner, AuditLogFilters())
                self.assertEqual(response.items[0].category, category)

    def test_non_platform_owner_is_denied(self):
        user = self.owner.model_copy(update={"role": "COMPANY_ADMIN", "company_id": uuid4()})
        with self.assertRaisesRegex(Exception, "Platform Owner access"):
            self.service.list(user, AuditLogFilters())


if __name__ == "__main__":
    unittest.main()
