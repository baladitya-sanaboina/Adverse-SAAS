from math import ceil

from app.repositories.audit_log_repository import AuditLogRepository
from app.schemas.audit_logs import (
    AuditLogFilters,
    AuditLogListResponse,
    AuditLogResponse,
    AuditLogSummaryResponse,
)
from app.schemas.authentication import AuthContext
from app.services.authentication_service import AuthenticationError


class AuditLogService:
    def __init__(self, repository: AuditLogRepository | None = None):
        self.repository = repository or AuditLogRepository()

    def _authorize(self, context: AuthContext) -> None:
        if context.role != "PLATFORM_OWNER" or not self.repository.actor_is_platform_owner(
            context.user_id
        ):
            raise AuthenticationError(
                403, "PLATFORM_OWNER_REQUIRED", "Platform Owner access is required."
            )

    def list(self, context: AuthContext, filters: AuditLogFilters) -> AuditLogListResponse:
        self._authorize(context)
        records, total = self.repository.list_logs(filters)
        categories = self.repository.summary()
        return AuditLogListResponse(
            items=[AuditLogResponse(**record.__dict__) for record in records],
            page=filters.page,
            page_size=filters.page_size,
            total=total,
            total_pages=ceil(total / filters.page_size) if total else 0,
            summary=AuditLogSummaryResponse(total=sum(categories.values()), categories=categories),
        )

    def is_ready(self) -> bool:
        return self.repository.is_ready()


audit_log_service = AuditLogService()
