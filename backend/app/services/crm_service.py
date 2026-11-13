from uuid import UUID

from app.repositories.crm_repository import (
    CrmConflict,
    CrmReferenceError,
    CrmRepository,
    LeadRecord,
    OpportunityRecord,
)
from app.schemas.authentication import AuthContext
from app.schemas.crm import (
    CrmOption,
    CrmOptionsResponse,
    LeadCreate,
    LeadListFilters,
    LeadListResponse,
    LeadResponse,
    LeadUpdate,
    OpportunityCreate,
    OpportunityListFilters,
    OpportunityListResponse,
    OpportunityResponse,
    OpportunityUpdate,
)
from app.services.authentication_service import AuthenticationError
from app.services.permission_service import validate_user_action_access


class CrmService:
    def __init__(self, repository: CrmRepository | None = None):
        self.repository = repository or CrmRepository()

    @staticmethod
    def _authorize(context: AuthContext, action: str) -> UUID:
        if context.user_type != "company" or context.company_id is None:
            raise AuthenticationError(
                403, "COMPANY_CONTEXT_REQUIRED", "Company access is required."
            )
        if not validate_user_action_access(str(context.user_id), context.role, "CRM", action):
            raise AuthenticationError(
                403,
                f"CRM_{action}_REQUIRED",
                f"CRM {action.lower()} permission is required.",
            )
        return context.company_id

    @staticmethod
    def _lead(record: LeadRecord) -> LeadResponse:
        return LeadResponse(**record.__dict__)

    @staticmethod
    def _opportunity(record: OpportunityRecord) -> OpportunityResponse:
        return OpportunityResponse(**record.__dict__)

    @staticmethod
    def _reference_error(error: CrmReferenceError) -> AuthenticationError:
        labels = {
            "owner": "The selected owner was not found as an active employee in this company.",
            "client": "The selected client was not found in this company.",
            "lead": "The selected lead was not found in this company.",
            "lead_client": "The selected lead belongs to a different client.",
        }
        return AuthenticationError(
            404,
            f"CRM_{error.reference.upper()}_NOT_FOUND",
            labels[error.reference],
        )

    def create_lead(self, context: AuthContext, request: LeadCreate) -> LeadResponse:
        company_id = self._authorize(context, "CREATE")
        try:
            record = self.repository.create_lead(
                company_id, context.user_id, request.model_dump(mode="python")
            )
        except CrmConflict as error:
            raise AuthenticationError(
                409, "LEAD_EMAIL_EXISTS", "A lead with this email already exists in this company."
            ) from error
        except CrmReferenceError as error:
            raise self._reference_error(error) from error
        return self._lead(record)

    def options(self, context: AuthContext) -> CrmOptionsResponse:
        company_id = self._authorize(context, "VIEW")
        owners, clients = self.repository.list_options(company_id)
        return CrmOptionsResponse(
            owners=[CrmOption(id=item[0], name=item[1]) for item in owners],
            clients=[CrmOption(id=item[0], name=item[1]) for item in clients],
        )

    def list_leads(self, context: AuthContext, filters: LeadListFilters) -> LeadListResponse:
        company_id = self._authorize(context, "VIEW")
        records, total = self.repository.list_leads(company_id, filters)
        return LeadListResponse(
            items=[self._lead(record) for record in records],
            page=filters.page,
            page_size=filters.page_size,
            total=total,
            total_pages=(total + filters.page_size - 1) // filters.page_size,
        )

    def get_lead(self, context: AuthContext, lead_id: UUID) -> LeadResponse:
        company_id = self._authorize(context, "VIEW")
        record = self.repository.get_lead(company_id, lead_id)
        if record is None:
            raise AuthenticationError(404, "LEAD_NOT_FOUND", "Lead was not found.")
        return self._lead(record)

    def update_lead(self, context: AuthContext, lead_id: UUID, request: LeadUpdate) -> LeadResponse:
        company_id = self._authorize(context, "EDIT")
        try:
            record = self.repository.update_lead(
                company_id,
                context.user_id,
                lead_id,
                request.model_dump(mode="python", exclude_unset=True),
            )
        except CrmConflict as error:
            raise AuthenticationError(
                409, "LEAD_EMAIL_EXISTS", "A lead with this email already exists in this company."
            ) from error
        except CrmReferenceError as error:
            raise self._reference_error(error) from error
        if record is None:
            raise AuthenticationError(404, "LEAD_NOT_FOUND", "Lead was not found.")
        return self._lead(record)

    def create_opportunity(
        self, context: AuthContext, request: OpportunityCreate
    ) -> OpportunityResponse:
        company_id = self._authorize(context, "CREATE")
        try:
            record = self.repository.create_opportunity(
                company_id, context.user_id, request.model_dump(mode="python")
            )
        except CrmReferenceError as error:
            raise self._reference_error(error) from error
        return self._opportunity(record)

    def list_opportunities(
        self, context: AuthContext, filters: OpportunityListFilters
    ) -> OpportunityListResponse:
        company_id = self._authorize(context, "VIEW")
        records, total = self.repository.list_opportunities(company_id, filters)
        return OpportunityListResponse(
            items=[self._opportunity(record) for record in records],
            page=filters.page,
            page_size=filters.page_size,
            total=total,
            total_pages=(total + filters.page_size - 1) // filters.page_size,
        )

    def get_opportunity(self, context: AuthContext, opportunity_id: UUID) -> OpportunityResponse:
        company_id = self._authorize(context, "VIEW")
        record = self.repository.get_opportunity(company_id, opportunity_id)
        if record is None:
            raise AuthenticationError(404, "OPPORTUNITY_NOT_FOUND", "Opportunity was not found.")
        return self._opportunity(record)

    def update_opportunity(
        self,
        context: AuthContext,
        opportunity_id: UUID,
        request: OpportunityUpdate,
    ) -> OpportunityResponse:
        company_id = self._authorize(context, "EDIT")
        try:
            record = self.repository.update_opportunity(
                company_id,
                context.user_id,
                opportunity_id,
                request.model_dump(mode="python", exclude_unset=True),
            )
        except CrmReferenceError as error:
            raise self._reference_error(error) from error
        if record is None:
            raise AuthenticationError(404, "OPPORTUNITY_NOT_FOUND", "Opportunity was not found.")
        return self._opportunity(record)

    def is_ready(self) -> bool:
        return self.repository.is_ready()


crm_service = CrmService()
