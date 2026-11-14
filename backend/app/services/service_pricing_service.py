from uuid import UUID

from app.repositories.service_pricing_repository import (
    CompanyServiceRecord,
    PricingOverviewItemRecord,
    ServiceCatalogConflict,
    ServiceCatalogReferenceError,
    ServiceDeleteBlocked,
    ServicePricingConflict,
    ServicePricingRecord,
    ServicePricingRepository,
    ServicePricingScope,
)
from app.schemas.authentication import AuthContext
from app.schemas.service_pricing import (
    CompanyServiceCreate,
    CompanyServiceDetailResponse,
    CompanyServiceListFilters,
    CompanyServiceListResponse,
    CompanyServiceResponse,
    CompanyServiceUpdate,
    PricingChangeRequest,
    PricingOverviewResponse,
    PricingSubjectSummary,
    ServicePricingRecordResponse,
    SubjectServicePricingItemResponse,
)
from app.services.authentication_service import AuthenticationError
from app.services.permission_service import validate_user_action_access


class ServicePricingService:
    def __init__(self, repository: ServicePricingRepository | None = None):
        self.repository = repository or ServicePricingRepository()

    @staticmethod
    def _authorize(context: AuthContext, action: str) -> UUID:
        if context.role != "COMPANY_ADMIN" or context.company_id is None:
            raise AuthenticationError(
                403,
                "COMPANY_ADMIN_REQUIRED",
                "Only a Company Admin can manage services and pricing.",
            )
        if not validate_user_action_access(str(context.user_id), context.role, "SETTINGS", action):
            raise AuthenticationError(
                403,
                f"SETTINGS_{action}_REQUIRED",
                f"Settings {action.lower()} permission is required.",
            )
        return context.company_id

    @staticmethod
    def _service_response(record: CompanyServiceRecord) -> CompanyServiceResponse:
        return CompanyServiceResponse(**record.__dict__)

    @staticmethod
    def _pricing_record_response(record: ServicePricingRecord) -> ServicePricingRecordResponse:
        return ServicePricingRecordResponse(
            id=record.id,
            scope=record.scope,
            pricing_model=record.pricing_model,
            amount=record.amount,
            currency=record.currency,
            notes=record.notes,
            effective_from=record.effective_from,
            effective_to=record.effective_to,
            created_by_id=record.created_by_id,
            created_by_name=record.created_by_name,
            created_at=record.created_at,
        )

    def list_services(
        self, context: AuthContext, filters: CompanyServiceListFilters
    ) -> CompanyServiceListResponse:
        company_id = self._authorize(context, "VIEW")
        records, total = self.repository.list_services(company_id, filters)
        return CompanyServiceListResponse(
            items=[self._service_response(item) for item in records],
            page=filters.page,
            page_size=filters.page_size,
            total=total,
            total_pages=max(1, (total + filters.page_size - 1) // filters.page_size),
        )

    def get_service(self, context: AuthContext, service_id: UUID) -> CompanyServiceDetailResponse:
        company_id = self._authorize(context, "VIEW")
        record = self.repository.get_service(company_id, service_id)
        if record is None:
            raise AuthenticationError(404, "SERVICE_NOT_FOUND", "Service was not found.")
        return CompanyServiceDetailResponse(**record.__dict__)

    def create_service(
        self, context: AuthContext, request: CompanyServiceCreate
    ) -> CompanyServiceResponse:
        company_id = self._authorize(context, "MANAGE")
        payload = request.model_dump()
        payload["code"] = self.repository.service_code(request.name)
        try:
            record = self.repository.create_service(company_id, context.user_id, payload)
        except ServiceCatalogConflict as error:
            code = "SERVICE_NAME_EXISTS" if error.field == "name" else "SERVICE_CODE_EXISTS"
            detail = (
                "A service with this name already exists."
                if error.field == "name"
                else "This service code is already in use."
            )
            raise AuthenticationError(409, code, detail) from error
        return self._service_response(record)

    def update_service(
        self, context: AuthContext, service_id: UUID, request: CompanyServiceUpdate
    ) -> CompanyServiceResponse:
        company_id = self._authorize(context, "MANAGE")
        payload = request.model_dump(exclude_unset=True)
        try:
            record = self.repository.update_service(
                company_id, context.user_id, service_id, payload
            )
        except ServiceCatalogConflict as error:
            code = "SERVICE_NAME_EXISTS" if error.field == "name" else "SERVICE_CODE_EXISTS"
            detail = (
                "A service with this name already exists."
                if error.field == "name"
                else "This service code is already in use."
            )
            raise AuthenticationError(409, code, detail) from error
        if record is None:
            raise AuthenticationError(404, "SERVICE_NOT_FOUND", "Service was not found.")
        return self._service_response(record)

    def delete_service(self, context: AuthContext, service_id: UUID) -> None:
        company_id = self._authorize(context, "MANAGE")
        try:
            deleted = self.repository.delete_service(company_id, context.user_id, service_id)
        except ServiceDeleteBlocked as error:
            raise AuthenticationError(
                409,
                "SERVICE_DELETE_BLOCKED",
                "This service already has pricing history. Deactivate it instead of deleting it.",
            ) from error
        if not deleted:
            raise AuthenticationError(404, "SERVICE_NOT_FOUND", "Service was not found.")

    def get_client_pricing(
        self, context: AuthContext, client_id: UUID, include_history: bool
    ) -> PricingOverviewResponse:
        company_id = self._authorize(context, "VIEW")
        return self._pricing_overview(company_id, "CLIENT", client_id, include_history)

    def set_client_pricing(
        self,
        context: AuthContext,
        client_id: UUID,
        service_id: UUID,
        request: PricingChangeRequest,
    ) -> ServicePricingRecordResponse:
        company_id = self._authorize(context, "MANAGE")
        return self._set_pricing(
            company_id, context.user_id, "CLIENT", client_id, service_id, request
        )

    def get_manager_pricing(
        self, context: AuthContext, manager_user_id: UUID, include_history: bool
    ) -> PricingOverviewResponse:
        company_id = self._authorize(context, "VIEW")
        return self._pricing_overview(company_id, "MANAGER", manager_user_id, include_history)

    def get_pricing_overview_for_subject(
        self,
        company_id: UUID,
        scope: ServicePricingScope,
        subject_id: UUID,
        *,
        include_history: bool,
    ) -> PricingOverviewResponse:
        return self._pricing_overview(company_id, scope, subject_id, include_history)

    def set_manager_pricing(
        self,
        context: AuthContext,
        manager_user_id: UUID,
        service_id: UUID,
        request: PricingChangeRequest,
    ) -> ServicePricingRecordResponse:
        company_id = self._authorize(context, "MANAGE")
        return self._set_pricing(
            company_id, context.user_id, "MANAGER", manager_user_id, service_id, request
        )

    def _set_pricing(
        self,
        company_id: UUID,
        actor_id: UUID,
        scope: ServicePricingScope,
        subject_id: UUID,
        service_id: UUID,
        request: PricingChangeRequest,
    ) -> ServicePricingRecordResponse:
        payload = request.model_dump(exclude_none=True)
        try:
            record = self.repository.set_pricing(
                company_id, actor_id, scope, subject_id, service_id, payload
            )
        except ServiceCatalogReferenceError as error:
            if error.reference == "service":
                raise AuthenticationError(
                    404, "SERVICE_NOT_FOUND", "Service was not found."
                ) from error
            if error.reference == "client":
                raise AuthenticationError(
                    404, "CLIENT_NOT_FOUND", "Client was not found."
                ) from error
            raise AuthenticationError(404, "MANAGER_NOT_FOUND", "Manager was not found.") from error
        except ServicePricingConflict as error:
            if error.reason == "service_inactive":
                raise AuthenticationError(
                    409,
                    "SERVICE_INACTIVE",
                    "Inactive services cannot receive new pricing changes.",
                ) from error
            raise AuthenticationError(
                409,
                "PRICING_EFFECTIVE_DATE_CONFLICT",
                "A pricing configuration already exists for that effective date.",
            ) from error
        return self._pricing_record_response(record)

    def _pricing_overview(
        self,
        company_id: UUID,
        scope: ServicePricingScope,
        subject_id: UUID,
        include_history: bool,
    ) -> PricingOverviewResponse:
        subject = self.repository.get_subject(company_id, scope, subject_id)
        if subject is None:
            code = "CLIENT_NOT_FOUND" if scope == "CLIENT" else "MANAGER_NOT_FOUND"
            label = "Client" if scope == "CLIENT" else "Manager"
            raise AuthenticationError(404, code, f"{label} was not found.")
        items = self.repository.list_pricing_overview(company_id, scope, subject_id)
        history = (
            self.repository.list_pricing_history(company_id, scope, subject_id)
            if include_history
            else ()
        )
        history_by_service: dict[UUID, list[ServicePricingRecordResponse]] = {}
        for entry in history:
            if entry.service_id is None:
                continue
            history_by_service.setdefault(entry.service_id, []).append(
                self._pricing_record_response(entry)
            )
        response_items = [self._overview_response_item(item, history_by_service) for item in items]
        configured = sum(1 for item in response_items if item.configured)
        return PricingOverviewResponse(
            scope=scope,
            subject=PricingSubjectSummary(
                id=subject.id,
                name=subject.name,
                subtitle=subject.subtitle,
            ),
            items=response_items,
            total_services=len(response_items),
            configured_services=configured,
            missing_services=max(0, len(response_items) - configured),
        )

    def _overview_response_item(
        self,
        item: PricingOverviewItemRecord,
        history_by_service: dict[UUID, list[ServicePricingRecordResponse]],
    ) -> SubjectServicePricingItemResponse:
        current_rate = None
        if item.current_rate_id is not None:
            current_rate = ServicePricingRecordResponse(
                id=item.current_rate_id,
                scope=item.current_rate_scope or "CLIENT",
                pricing_model=item.current_pricing_model or item.default_pricing_model,
                amount=item.current_amount or 0,
                currency=item.current_currency or "INR",
                notes=item.current_notes or "",
                effective_from=item.current_effective_from or item.current_created_at,
                effective_to=item.current_effective_to,
                created_by_id=item.current_created_by_id or item.service_id,
                created_by_name=item.current_created_by_name or "Unknown",
                created_at=item.current_created_at or item.current_effective_from,
            )
        return SubjectServicePricingItemResponse(
            service_id=item.service_id,
            service_name=item.service_name,
            service_code=item.service_code,
            service_description=item.service_description,
            service_status=item.service_status,
            default_pricing_model=item.default_pricing_model,
            configured=current_rate is not None,
            current_rate=current_rate,
            history_count=item.history_count,
            history=history_by_service.get(item.service_id, []),
        )

    def is_ready(self) -> bool:
        return self.repository.is_ready()


service_pricing_service = ServicePricingService()
