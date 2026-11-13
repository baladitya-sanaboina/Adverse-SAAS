from datetime import UTC, datetime
from math import ceil
from uuid import UUID

from app.repositories.subscription_management_repository import (
    CompanyPlanRecord,
    PlanRecord,
    SubscriptionManagementRepository,
)
from app.schemas.authentication import AuthContext
from app.schemas.subscription_management import (
    CompanyPlanAssignmentRequest,
    CompanyPlanResponse,
    PlanCreateRequest,
    PlanListFilters,
    PlanListResponse,
    PlanResponse,
    PlanUpdateRequest,
    SubscriptionValidationResponse,
)
from app.services.authentication_service import AuthenticationError
from app.services.permission_service import validate_user_action_access


class SubscriptionManagementService:
    def __init__(self, repository: SubscriptionManagementRepository | None = None):
        self.repository = repository or SubscriptionManagementRepository()

    @staticmethod
    def _authorize(context: AuthContext, action: str) -> None:
        if not validate_user_action_access(
            str(context.user_id), context.role, "SUBSCRIPTIONS", action
        ):
            raise AuthenticationError(
                403, "PERMISSION_DENIED", f"{action} access to SUBSCRIPTIONS is required."
            )

    @staticmethod
    def _response(record: PlanRecord) -> PlanResponse:
        return PlanResponse(**record.__dict__)

    def create(self, context: AuthContext, request: PlanCreateRequest) -> PlanResponse:
        self._authorize(context, "CREATE")
        if self.repository.code_exists(request.code):
            raise AuthenticationError(409, "PLAN_CODE_EXISTS", "Plan code already exists.")
        return self._response(self.repository.create_plan(context.user_id, request))

    def list(self, context: AuthContext, filters: PlanListFilters) -> PlanListResponse:
        self._authorize(context, "VIEW")
        records, total = self.repository.list_plans(filters)
        return PlanListResponse(
            items=[self._response(item) for item in records],
            page=filters.page,
            page_size=filters.page_size,
            total=total,
            total_pages=ceil(total / filters.page_size) if total else 0,
        )

    def get(self, context: AuthContext, plan_id: UUID) -> PlanResponse:
        self._authorize(context, "VIEW")
        record = self.repository.get_plan(plan_id)
        if not record:
            raise AuthenticationError(404, "PLAN_NOT_FOUND", "Subscription plan does not exist.")
        return self._response(record)

    def update(
        self, context: AuthContext, plan_id: UUID, request: PlanUpdateRequest
    ) -> PlanResponse:
        self._authorize(context, "EDIT")
        record = self.repository.update_plan(context.user_id, plan_id, request)
        if not record:
            raise AuthenticationError(404, "PLAN_NOT_FOUND", "Subscription plan does not exist.")
        return self._response(record)

    def assign(
        self, context: AuthContext, company_id: UUID, request: CompanyPlanAssignmentRequest
    ) -> CompanyPlanResponse:
        self._authorize(context, "ASSIGN")
        activation = request.activation_date or datetime.now(UTC)
        if request.expiration_date and request.expiration_date <= activation:
            raise AuthenticationError(
                422, "INVALID_SUBSCRIPTION_PERIOD", "Expiration must be after activation."
            )
        try:
            record = self.repository.assign_plan(
                context.user_id,
                company_id,
                request.plan_id,
                activation,
                request.expiration_date,
            )
        except ValueError as error:
            raise AuthenticationError(409, "PLAN_INACTIVE", str(error)) from error
        if not record:
            if not self.repository.get_plan(request.plan_id):
                raise AuthenticationError(
                    404, "PLAN_NOT_FOUND", "Subscription plan does not exist."
                )
            raise AuthenticationError(404, "COMPANY_NOT_FOUND", "Company does not exist.")
        return self._assignment_response(record)

    def _assignment_response(self, record: CompanyPlanRecord) -> CompanyPlanResponse:
        if record.previous_display_order is None:
            change = "ASSIGNED"
        elif record.plan.display_order > record.previous_display_order:
            change = "UPGRADE"
        elif record.plan.display_order < record.previous_display_order:
            change = "DOWNGRADE"
        else:
            change = "CHANGED"
        return CompanyPlanResponse(
            company_id=record.company_id,
            company_name=record.company_name,
            plan=self._response(record.plan),
            status=record.status,
            activation_date=record.activation_date,
            expiration_date=record.expiration_date,
            change_type=change,
        )

    def validate(
        self,
        company_id: UUID,
        feature_code: str | None = None,
        limit_code: str | None = None,
    ) -> SubscriptionValidationResponse:
        plan = self.repository.get_company_plan(company_id)
        if not plan or plan.status != "ACTIVE":
            return SubscriptionValidationResponse(
                company_id=company_id,
                plan_code=plan.code if plan else "UNASSIGNED",
                feature_code=feature_code,
                limit_code=limit_code,
                allowed=False,
            )
        enabled = feature_code is None or plan.features.get(feature_code, False)
        limit = plan.limits.get(limit_code) if limit_code else None
        return SubscriptionValidationResponse(
            company_id=company_id,
            plan_code=plan.code,
            feature_code=feature_code,
            limit_code=limit_code,
            allowed=enabled,
            limit=limit,
            unlimited=bool(limit_code and limit is None),
        )

    def is_ready(self) -> bool:
        return self.repository.is_ready()


subscription_management_service = SubscriptionManagementService()
