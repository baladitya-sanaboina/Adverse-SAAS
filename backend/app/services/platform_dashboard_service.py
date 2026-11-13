from app.core.redis_connectivity import redis_is_reachable
from app.core.settings import settings
from app.database.connectivity import get_database_health
from app.repositories.platform_dashboard_repository import PlatformDashboardRepository
from app.schemas.authentication import AuthContext
from app.schemas.platform_dashboard import (
    PlatformActivity,
    PlatformDashboardResponse,
    PlatformQuickAction,
    PlatformStatistics,
    PlatformSystemHealth,
)
from app.services.authentication_service import AuthenticationError
from app.services.email_service import email_service


class PlatformDashboardService:
    def __init__(self, repository: PlatformDashboardRepository | None = None):
        self.repository = repository or PlatformDashboardRepository()

    def get_dashboard(self, context: AuthContext) -> PlatformDashboardResponse:
        if context.role != "PLATFORM_OWNER":
            raise AuthenticationError(
                403, "PLATFORM_OWNER_REQUIRED", "Platform Owner access is required."
            )
        statistics = self.repository.load_statistics()
        activities = self.repository.load_recent_activities()
        database_healthy = get_database_health().connected
        return PlatformDashboardResponse(
            statistics=PlatformStatistics(**statistics.__dict__),
            recent_activities=[PlatformActivity(**activity.__dict__) for activity in activities],
            system_health=PlatformSystemHealth(
                backend="healthy",
                database="healthy" if database_healthy else "unavailable",
                redis="healthy" if redis_is_reachable() else "unavailable",
                smtp="healthy" if email_service.is_ready() else "unavailable",
                storage="healthy" if settings.storage_provider else "unavailable",
                api_version=settings.app_version,
            ),
            quick_actions=[
                PlatformQuickAction(label="Create Developer", href="/developers?mode=create"),
                PlatformQuickAction(label="View Developers", href="/developers"),
                PlatformQuickAction(label="View Companies", href="/companies"),
                PlatformQuickAction(label="View Audit Logs", href="/logs"),
                PlatformQuickAction(label="Platform Settings", href="/settings"),
            ],
        )

    def is_ready(self) -> bool:
        return self.repository.foundation_is_ready()


platform_dashboard_service = PlatformDashboardService()
