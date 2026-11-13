from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from app.repositories.company_dashboard_repository import CompanyDashboardRepository
from app.repositories.finance_repository import FinanceRepository
from app.schemas.authentication import AuthContext
from app.schemas.company_dashboard import (
    CompanyDashboardActivity,
    CompanyDashboardCompany,
    CompanyDashboardQuickAction,
    CompanyDashboardResponse,
    CompanyDashboardStatistics,
    CompanyDashboardUser,
)
from app.services.authentication_service import AuthenticationError
from app.services.permission_service import validate_user_action_access
from app.services.production_rules import money, resolve_period


class CompanyDashboardService:
    def __init__(
        self,
        repository: CompanyDashboardRepository | None = None,
        finance_repository: FinanceRepository | None = None,
    ):
        self.repository = repository or CompanyDashboardRepository()
        self.finance = finance_repository or FinanceRepository()

    def _month_revenue(self, context: AuthContext, company_id: UUID) -> str | None:
        """This month's approved revenue for the Finance card, or None to keep the card empty."""
        if not validate_user_action_access(str(context.user_id), context.role, "FINANCE", "VIEW"):
            return None
        try:
            zone_name = self.finance.company_timezone(company_id)
            today = datetime.now(ZoneInfo(zone_name)).date()
            start, end = resolve_period("this_month", today)
            revenue, _, _ = self.finance.revenue_in_range(company_id, zone_name, start, end)
            currency = self.finance.company_currency(company_id)
        except Exception:
            return None
        return f"{currency} {money(revenue):,.2f}"

    @staticmethod
    def _authorize(context: AuthContext) -> None:
        if context.role != "COMPANY_ADMIN" or context.company_id is None:
            raise AuthenticationError(
                403, "COMPANY_ADMIN_REQUIRED", "Company Admin access is required."
            )
        if not validate_user_action_access(str(context.user_id), context.role, "DASHBOARD", "VIEW"):
            raise AuthenticationError(
                403, "DASHBOARD_VIEW_REQUIRED", "Dashboard view permission is required."
            )

    def get_dashboard(self, context: AuthContext) -> CompanyDashboardResponse:
        self._authorize(context)
        assert context.company_id is not None
        record = self.repository.load(context.company_id, context.user_id)
        if record is None:
            raise AuthenticationError(
                404, "COMPANY_DASHBOARD_NOT_FOUND", "Company dashboard context was not found."
            )
        activities = self.repository.load_recent_activity(context.company_id)
        action_specs = (
            ("Add Employee", "/employees?mode=create", "EMPLOYEES", "CREATE"),
            ("Add Client", "/clients?mode=create", "CLIENTS", "CREATE"),
            ("Create Task", "/tasks?mode=create", "TASKS", "CREATE"),
        )
        quick_actions = [
            CompanyDashboardQuickAction(label=label, href=href, module=module, action=action)
            for label, href, module, action in action_specs
            if validate_user_action_access(str(context.user_id), context.role, module, action)
        ]
        return CompanyDashboardResponse(
            company=CompanyDashboardCompany(
                id=record.company_id, name=record.company_name, logo_url=record.logo_url
            ),
            current_user=CompanyDashboardUser(
                id=record.user_id, name=record.user_name, role="COMPANY_ADMIN"
            ),
            statistics=CompanyDashboardStatistics(
                employees=record.employees,
                projects=record.projects,
                clients=record.clients,
                finance_total=self._month_revenue(context, context.company_id),
            ),
            recent_activity=[
                CompanyDashboardActivity(**activity.__dict__) for activity in activities
            ],
            quick_actions=quick_actions,
        )

    def is_ready(self) -> bool:
        return self.repository.is_ready()


company_dashboard_service = CompanyDashboardService()
