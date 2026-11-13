import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from uuid import uuid4

from app.repositories.subscription_enforcement_repository import EnforcementSnapshot
from app.schemas.authentication import AuthContext
from app.schemas.subscription_enforcement import SubscriptionValidationRequest
from app.services.authentication_service import AuthenticationError
from app.services.subscription_enforcement_service import SubscriptionEnforcementService


class FakeEnforcementRepository:
    def __init__(self):
        self.company_id = uuid4()
        self.snapshot_value = EnforcementSnapshot(
            company_id=self.company_id,
            company_name="Acme",
            plan_id=uuid4(),
            plan_name="Starter",
            plan_code="STARTER",
            features={"CRM": True, "AI_FEATURES": False},
            limits={
                "MAX_EMPLOYEES": 10,
                "MAX_CLIENTS": 10,
                "MAX_PROJECTS": None,
                "MAX_STORAGE_GB": 5,
            },
            employees_used=8,
            clients_used=9,
            projects_used=200,
            storage_used_bytes=5 * 1024**3,
        )
        self.events: list[str] = []
        self.alerts: list[tuple[str, str]] = []

    def snapshot(self, company_id):
        return self.snapshot_value if company_id == self.company_id else None

    def company_exists(self, company_id):
        return company_id == self.company_id

    def record_event(self, *args, **kwargs):
        self.events.append(args[3])

    def sync_alert(self, company_id, resource_code, level, message):
        self.alerts.append((resource_code, level))

    def is_ready(self):
        return True


class SubscriptionEnforcementTests(unittest.TestCase):
    def setUp(self):
        self.repository = FakeEnforcementRepository()
        self.service = SubscriptionEnforcementService(self.repository)  # type: ignore[arg-type]
        now = datetime.now(UTC)
        self.context = AuthContext(
            user_id=uuid4(),
            role="PLATFORM_OWNER",
            company_id=None,
            user_type="platform",
            session_id=uuid4(),
            issued_at=now,
            expires_at=now + timedelta(minutes=30),
        )

    @patch(
        "app.services.subscription_enforcement_service.validate_user_action_access",
        return_value=True,
    )
    def test_usage_thresholds_unlimited_and_storage(self, _permission):
        usage = self.service.usage(self.context, self.repository.company_id)
        metrics = {item.code: item for item in usage.usage}
        self.assertEqual(metrics["MAX_EMPLOYEES"].state, "WARNING")
        self.assertEqual(metrics["MAX_CLIENTS"].state, "HIGH_USAGE")
        self.assertEqual(metrics["MAX_PROJECTS"].state, "UNLIMITED")
        self.assertEqual(metrics["MAX_STORAGE_GB"].state, "LIMIT_REACHED")
        self.assertTrue(usage.upgrade_recommended)

    def test_feature_access_and_block_audit(self):
        allowed = self.service.validate_feature(self.repository.company_id, "CRM")
        denied = self.service.validate_feature(self.repository.company_id, "AI_FEATURES")
        self.assertTrue(allowed.allowed)
        self.assertFalse(denied.allowed)
        self.assertEqual(self.repository.events, ["PLAN_VALIDATED", "FEATURE_BLOCKED"])

    def test_limit_enforcement_and_upgrade_audit(self):
        result = self.service.validate_limit(
            self.repository.company_id, "MAX_EMPLOYEES", requested_increment=3
        )
        self.assertFalse(result.allowed)
        self.assertEqual(result.state, "LIMIT_REACHED")
        self.assertTrue(result.upgrade_recommended)
        self.assertEqual(self.repository.events, ["LIMIT_EXCEEDED", "UPGRADE_RECOMMENDED"])
        with self.assertRaises(AuthenticationError):
            self.service.enforce_limit(
                self.repository.company_id, "MAX_STORAGE_GB", requested_increment=1
            )

    def test_unlimited_project_limit_allows_growth(self):
        result = self.service.validate_limit(
            self.repository.company_id, "MAX_PROJECTS", requested_increment=10000
        )
        self.assertTrue(result.allowed)
        self.assertTrue(result.unlimited)
        self.assertIn(("MAX_PROJECTS", "UNLIMITED"), self.repository.alerts)

    def test_validation_request_requires_exactly_one_target(self):
        with self.assertRaises(ValueError):
            SubscriptionValidationRequest()
        with self.assertRaises(ValueError):
            SubscriptionValidationRequest(feature_code="CRM", resource_code="MAX_EMPLOYEES")


if __name__ == "__main__":
    unittest.main()
