from math import ceil
from uuid import UUID

from app.repositories.company_management_repository import (
    CompanyManagementRepository,
    CompanyRecord,
)
from app.schemas.authentication import AuthContext
from app.schemas.company_management import (
    CompanyAdminResponse,
    CompanyAuditResponse,
    CompanyListFilters,
    CompanyListResponse,
    CompanyResponse,
    CompanyStatisticsResponse,
    CompanyStatusRequest,
    CompanySubscriptionSummary,
    CompanySummaryResponse,
)
from app.services.authentication_service import AuthenticationError
from app.services.permission_service import validate_user_action_access


class CompanyManagementService:
    def __init__(self, repository: CompanyManagementRepository | None = None):
        self.repository = repository or CompanyManagementRepository()

    @staticmethod
    def _authorize(context: AuthContext, action: str) -> None:
        if not validate_user_action_access(str(context.user_id), context.role, "COMPANIES", action):
            raise AuthenticationError(
                403, "PERMISSION_DENIED", f"{action} access to COMPANIES is required."
            )

    def _response(self, record: CompanyRecord, include_audits: bool = False) -> CompanyResponse:
        audits = self.repository.audits_for(record.id) if include_audits else ()
        return CompanyResponse(
            id=record.id,
            name=record.name,
            code=record.code,
            contact_email=record.contact_email,
            subscription_plan=record.subscription_plan,
            status=record.status,
            company_admin=CompanyAdminResponse(
                id=record.admin_id,
                name=record.admin_name,
                email=record.admin_email,
                status=record.admin_status,
            ),
            statistics=CompanyStatisticsResponse(
                total_users=record.total_users,
                active_users=record.active_users,
                inactive_users=record.inactive_users,
            ),
            created_at=record.created_at,
            updated_at=record.updated_at,
            recent_activity=[CompanyAuditResponse(**audit.__dict__) for audit in audits],
            subscription=CompanySubscriptionSummary(**self.repository.subscription_for(record.id)),
        )

    def list(self, context: AuthContext, filters: CompanyListFilters) -> CompanyListResponse:
        self._authorize(context, "VIEW")
        records, total = self.repository.list_companies(filters)
        summary = self.repository.summary()
        return CompanyListResponse(
            items=[self._response(record) for record in records],
            page=filters.page,
            page_size=filters.page_size,
            total=total,
            total_pages=ceil(total / filters.page_size) if total else 0,
            summary=CompanySummaryResponse(
                total=summary[0],
                active=summary[1],
                inactive=summary[2],
                suspended=summary[3],
                pending=summary[4],
            ),
        )

    def get(self, context: AuthContext, company_id: UUID) -> CompanyResponse:
        self._authorize(context, "VIEW")
        record = self.repository.get_company(company_id)
        if not record:
            raise AuthenticationError(404, "COMPANY_NOT_FOUND", "Company does not exist.")
        self.repository.record_view(context.user_id, company_id)
        return self._response(record, True)

    def update_status(
        self, context: AuthContext, company_id: UUID, request: CompanyStatusRequest
    ) -> CompanyResponse:
        self._authorize(context, "EDIT")
        record = self.repository.update_status(context.user_id, company_id, request.status)
        if not record:
            raise AuthenticationError(404, "COMPANY_NOT_FOUND", "Company does not exist.")
        return self._response(record, True)

    def is_ready(self) -> bool:
        return self.repository.is_ready()


company_management_service = CompanyManagementService()
