import unittest
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from app.repositories.platform_dashboard_repository import (
    PlatformActivityRecord,
    PlatformStatisticsRecord,
)
from app.schemas.authentication import AuthContext
from app.services.authentication_service import AuthenticationError
from app.services.platform_dashboard_service import PlatformDashboardService


class FakePlatformDashboardRepository:
    def load_statistics(self):
        return PlatformStatisticsRecord(3, 2, 8, 4, 12, 1, 5)

    def load_recent_activities(self, limit=8):
        return (
            PlatformActivityRecord("COMPANY_CREATED", "Acme", "Company created", datetime.now(UTC)),
        )

    def foundation_is_ready(self):
        return True


class PlatformDashboardTests(unittest.TestCase):
    def context(self, role="PLATFORM_OWNER"):
        now = datetime.now(UTC)
        return AuthContext(
            user_id=uuid4(),
            role=role,
            company_id=None,
            user_type="platform",
            session_id=uuid4(),
            issued_at=now,
            expires_at=now,
        )

    @patch("app.services.platform_dashboard_service.email_service.is_ready", return_value=True)
    @patch("app.services.platform_dashboard_service.redis_is_reachable", return_value=True)
    @patch(
        "app.services.platform_dashboard_service.get_database_health",
        return_value=SimpleNamespace(connected=True),
    )
    def test_dashboard_returns_statistics_activity_health_and_actions(self, *_):
        response = PlatformDashboardService(FakePlatformDashboardRepository()).get_dashboard(
            self.context()
        )
        self.assertEqual(response.statistics.total_companies, 3)
        self.assertEqual(response.recent_activities[0].subject, "Acme")
        self.assertEqual(response.system_health.database, "healthy")
        self.assertTrue(any(action.href == "/developers" for action in response.quick_actions))

    def test_non_platform_owner_is_rejected(self):
        with self.assertRaisesRegex(AuthenticationError, "Platform Owner"):
            PlatformDashboardService(FakePlatformDashboardRepository()).get_dashboard(
                self.context("DEVELOPER")
            )

    def test_service_readiness_uses_repository(self):
        self.assertTrue(PlatformDashboardService(FakePlatformDashboardRepository()).is_ready())


if __name__ == "__main__":
    unittest.main()
