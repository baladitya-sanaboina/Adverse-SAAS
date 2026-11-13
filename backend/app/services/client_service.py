from uuid import UUID

from app.repositories.client_repository import (
    ClientActivityRecord,
    ClientConflict,
    ClientContactRecord,
    ClientFeedbackRecord,
    ClientNoteRecord,
    ClientRecord,
    ClientReferenceError,
    ClientRepository,
)
from app.schemas.authentication import AuthContext
from app.schemas.client import (
    ClientActivityListResponse,
    ClientActivityResponse,
    ClientContactCreate,
    ClientContactListResponse,
    ClientContactResponse,
    ClientContactUpdate,
    ClientCreate,
    ClientDetailResponse,
    ClientFeedbackCreate,
    ClientFeedbackListResponse,
    ClientFeedbackResponse,
    ClientFeedbackUpdate,
    ClientListFilters,
    ClientListResponse,
    ClientNoteCreate,
    ClientNoteListResponse,
    ClientNoteResponse,
    ClientNoteUpdate,
    ClientPortalBillingSummaryResponse,
    ClientPortalDashboardResponse,
    ClientPortalPackageSummaryResponse,
    ClientPortalWorkSummaryResponse,
    ClientResponse,
    ClientUpdate,
)
from app.services.authentication_service import AuthenticationError
from app.services.permission_service import validate_user_action_access
from app.services.service_pricing_service import ServicePricingService, service_pricing_service


class ClientService:
    def __init__(
        self,
        repository: ClientRepository | None = None,
        pricing_service: ServicePricingService | None = None,
    ):
        self.repository = repository or ClientRepository()
        self.pricing_service = pricing_service or service_pricing_service

    @staticmethod
    def _authorize(context: AuthContext, action: str) -> UUID:
        if context.user_type != "company" or context.company_id is None:
            raise AuthenticationError(
                403, "COMPANY_CONTEXT_REQUIRED", "Company access is required."
            )
        if not validate_user_action_access(str(context.user_id), context.role, "CLIENTS", action):
            raise AuthenticationError(
                403,
                f"CLIENTS_{action}_REQUIRED",
                f"Clients {action.lower()} permission is required.",
            )
        return context.company_id

    @staticmethod
    def _client(record: ClientRecord) -> ClientResponse:
        return ClientResponse(**record.__dict__)

    @staticmethod
    def _contact(record: ClientContactRecord) -> ClientContactResponse:
        return ClientContactResponse(**record.__dict__)

    @classmethod
    def _authorize_internal(cls, context: AuthContext, action: str) -> UUID:
        company_id = cls._authorize(context, action)
        if context.role == "COMPANY_CLIENT":
            raise AuthenticationError(
                403,
                "CLIENT_HISTORY_INTERNAL_ONLY",
                "Internal client history is not available to client accounts.",
            )
        return company_id

    @staticmethod
    def _authorize_portal(context: AuthContext) -> UUID:
        if context.user_type != "company" or context.company_id is None:
            raise AuthenticationError(
                403, "COMPANY_CONTEXT_REQUIRED", "Company access is required."
            )
        if context.role != "COMPANY_CLIENT":
            raise AuthenticationError(
                403,
                "CLIENT_PORTAL_REQUIRED",
                "Only a Company Client can access the client portal dashboard.",
            )
        return context.company_id

    @staticmethod
    def _note(record: ClientNoteRecord) -> ClientNoteResponse:
        return ClientNoteResponse(**record.__dict__)

    @staticmethod
    def _feedback(record: ClientFeedbackRecord) -> ClientFeedbackResponse:
        return ClientFeedbackResponse(**record.__dict__)

    @staticmethod
    def _activity(record: ClientActivityRecord) -> ClientActivityResponse:
        return ClientActivityResponse(**record.__dict__)

    @staticmethod
    def _client_conflict(error: ClientConflict) -> AuthenticationError:
        if error.field == "email":
            return AuthenticationError(
                409,
                "CLIENT_EMAIL_EXISTS",
                "Client email already exists in this company.",
            )
        if error.field == "account_user":
            return AuthenticationError(
                409,
                "CLIENT_ACCOUNT_EXISTS",
                "This client login is already linked to another client.",
            )
        return AuthenticationError(
            409, "CLIENT_CODE_EXISTS", "Client code already exists in this company."
        )

    def create(self, context: AuthContext, request: ClientCreate) -> ClientResponse:
        company_id = self._authorize(context, "CREATE")
        try:
            record = self.repository.create(company_id, request.model_dump(mode="json"))
        except ClientConflict as error:
            raise self._client_conflict(error) from error
        return self._client(record)

    def list(self, context: AuthContext, filters: ClientListFilters) -> ClientListResponse:
        company_id = self._authorize(context, "VIEW")
        records, total = self.repository.list(company_id, filters)
        return ClientListResponse(
            items=[self._client(record) for record in records],
            page=filters.page,
            page_size=filters.page_size,
            total=total,
            total_pages=(total + filters.page_size - 1) // filters.page_size,
        )

    def get(self, context: AuthContext, client_id: UUID) -> ClientDetailResponse:
        company_id = self._authorize(context, "VIEW")
        record = self.repository.get(company_id, client_id)
        if record is None:
            raise AuthenticationError(404, "CLIENT_NOT_FOUND", "Client was not found.")
        contacts = self.repository.list_contacts(company_id, client_id)
        return ClientDetailResponse(
            **record.__dict__, contacts=[self._contact(contact) for contact in contacts]
        )

    def update(
        self, context: AuthContext, client_id: UUID, request: ClientUpdate
    ) -> ClientResponse:
        company_id = self._authorize(context, "EDIT")
        try:
            record = self.repository.update(
                company_id,
                client_id,
                context.user_id,
                request.model_dump(mode="json", exclude_unset=True),
            )
        except ClientConflict as error:
            raise self._client_conflict(error) from error
        if record is None:
            raise AuthenticationError(404, "CLIENT_NOT_FOUND", "Client was not found.")
        return self._client(record)

    def get_portal_dashboard(self, context: AuthContext) -> ClientPortalDashboardResponse:
        company_id = self._authorize_portal(context)
        record = self.repository.get_for_user(company_id, context.user_id)
        if record is None:
            raise AuthenticationError(
                404,
                "CLIENT_ACCOUNT_NOT_LINKED",
                "This client account is not linked to a client profile yet.",
            )
        contacts = self.repository.list_contacts(company_id, record.id)
        detail = ClientDetailResponse(
            **record.__dict__, contacts=[self._contact(contact) for contact in contacts]
        )
        pricing = self.pricing_service.get_pricing_overview_for_subject(
            company_id,
            "CLIENT",
            record.id,
            include_history=False,
        )
        packages = [
            ClientPortalPackageSummaryResponse(
                service_id=item.service_id,
                service_name=item.service_name,
                pricing_model=item.current_rate.pricing_model,
                amount=item.current_rate.amount,
                currency=item.current_rate.currency,
                billing_period_label="Monthly",
                notes=item.current_rate.notes,
            )
            for item in pricing.items
            if item.current_rate is not None
            and item.current_rate.pricing_model in {"MONTHLY_FIXED", "MONTHLY_PACKAGE"}
        ]
        return ClientPortalDashboardResponse(
            client=detail,
            pricing=pricing,
            packages=packages,
            work=ClientPortalWorkSummaryResponse(
                ready=False,
                message=(
                    "Task, approval, and deliverable workflows are not configured yet, so client work history remains unavailable."
                ),
                filters=[
                    "ALL",
                    "PENDING",
                    "IN_PROGRESS",
                    "SUBMITTED",
                    "APPROVED",
                    "COMPLETED",
                ],
            ),
            billing=ClientPortalBillingSummaryResponse(
                ready=False,
                message=(
                    "Billing totals and payment history will appear after approved task billing and payment records are implemented."
                ),
                monthly_billing=packages[0].amount if packages else None,
            ),
        )

    def create_contact(
        self, context: AuthContext, client_id: UUID, request: ClientContactCreate
    ) -> ClientContactResponse:
        company_id = self._authorize(context, "MANAGE")
        try:
            record = self.repository.create_contact(
                company_id, client_id, context.user_id, request.model_dump(mode="json")
            )
        except ClientReferenceError as error:
            raise AuthenticationError(404, "CLIENT_NOT_FOUND", "Client was not found.") from error
        except ClientConflict as error:
            raise AuthenticationError(
                409,
                "CLIENT_CONTACT_EMAIL_EXISTS",
                "Contact email already exists for this client.",
            ) from error
        return self._contact(record)

    def list_contacts(self, context: AuthContext, client_id: UUID) -> ClientContactListResponse:
        company_id = self._authorize(context, "VIEW")
        try:
            records = self.repository.list_contacts(company_id, client_id)
        except ClientReferenceError as error:
            raise AuthenticationError(404, "CLIENT_NOT_FOUND", "Client was not found.") from error
        return ClientContactListResponse(
            items=[self._contact(record) for record in records], total=len(records)
        )

    def update_contact(
        self,
        context: AuthContext,
        client_id: UUID,
        contact_id: UUID,
        request: ClientContactUpdate,
    ) -> ClientContactResponse:
        company_id = self._authorize(context, "MANAGE")
        try:
            record = self.repository.update_contact(
                company_id,
                client_id,
                contact_id,
                context.user_id,
                request.model_dump(mode="json", exclude_unset=True),
            )
        except ClientReferenceError as error:
            raise AuthenticationError(404, "CLIENT_NOT_FOUND", "Client was not found.") from error
        except ClientConflict as error:
            raise AuthenticationError(
                409,
                "CLIENT_CONTACT_EMAIL_EXISTS",
                "Contact email already exists for this client.",
            ) from error
        if record is None:
            raise AuthenticationError(
                404, "CLIENT_CONTACT_NOT_FOUND", "Client contact was not found."
            )
        return self._contact(record)

    def list_notes(self, context: AuthContext, client_id: UUID) -> ClientNoteListResponse:
        company_id = self._authorize_internal(context, "VIEW")
        try:
            records = self.repository.list_notes(company_id, client_id)
        except ClientReferenceError as error:
            raise AuthenticationError(404, "CLIENT_NOT_FOUND", "Client was not found.") from error
        return ClientNoteListResponse(
            items=[self._note(record) for record in records], total=len(records)
        )

    def create_note(
        self, context: AuthContext, client_id: UUID, request: ClientNoteCreate
    ) -> ClientNoteResponse:
        company_id = self._authorize_internal(context, "EDIT")
        try:
            record = self.repository.create_note(
                company_id, client_id, context.user_id, request.content
            )
        except ClientReferenceError as error:
            raise AuthenticationError(404, "CLIENT_NOT_FOUND", "Client was not found.") from error
        return self._note(record)

    def update_note(
        self, context: AuthContext, client_id: UUID, note_id: UUID, request: ClientNoteUpdate
    ) -> ClientNoteResponse:
        company_id = self._authorize_internal(context, "EDIT")
        try:
            record = self.repository.update_note(
                company_id, client_id, note_id, context.user_id, request.content
            )
        except ClientReferenceError as error:
            raise AuthenticationError(404, "CLIENT_NOT_FOUND", "Client was not found.") from error
        if record is None:
            raise AuthenticationError(404, "CLIENT_NOTE_NOT_FOUND", "Client note was not found.")
        return self._note(record)

    def delete_note(self, context: AuthContext, client_id: UUID, note_id: UUID) -> None:
        company_id = self._authorize_internal(context, "DELETE")
        try:
            deleted = self.repository.delete_note(company_id, client_id, note_id, context.user_id)
        except ClientReferenceError as error:
            raise AuthenticationError(404, "CLIENT_NOT_FOUND", "Client was not found.") from error
        if not deleted:
            raise AuthenticationError(404, "CLIENT_NOTE_NOT_FOUND", "Client note was not found.")

    def list_feedback(self, context: AuthContext, client_id: UUID) -> ClientFeedbackListResponse:
        company_id = self._authorize(context, "VIEW")
        try:
            records = self.repository.list_feedback(company_id, client_id)
        except ClientReferenceError as error:
            raise AuthenticationError(404, "CLIENT_NOT_FOUND", "Client was not found.") from error
        return ClientFeedbackListResponse(
            items=[self._feedback(record) for record in records], total=len(records)
        )

    def create_feedback(
        self, context: AuthContext, client_id: UUID, request: ClientFeedbackCreate
    ) -> ClientFeedbackResponse:
        company_id = self._authorize(context, "EDIT")
        try:
            record = self.repository.create_feedback(
                company_id, client_id, context.user_id, request.content
            )
        except ClientReferenceError as error:
            raise AuthenticationError(404, "CLIENT_NOT_FOUND", "Client was not found.") from error
        return self._feedback(record)

    def update_feedback(
        self,
        context: AuthContext,
        client_id: UUID,
        feedback_id: UUID,
        request: ClientFeedbackUpdate,
    ) -> ClientFeedbackResponse:
        company_id = self._authorize(context, "EDIT")
        try:
            record = self.repository.update_feedback(
                company_id, client_id, feedback_id, context.user_id, request.content
            )
        except ClientReferenceError as error:
            raise AuthenticationError(404, "CLIENT_NOT_FOUND", "Client was not found.") from error
        if record is None:
            raise AuthenticationError(
                404, "CLIENT_FEEDBACK_NOT_FOUND", "Client feedback was not found."
            )
        return self._feedback(record)

    def list_activity(self, context: AuthContext, client_id: UUID) -> ClientActivityListResponse:
        company_id = self._authorize_internal(context, "VIEW")
        try:
            records = self.repository.list_activity(company_id, client_id)
        except ClientReferenceError as error:
            raise AuthenticationError(404, "CLIENT_NOT_FOUND", "Client was not found.") from error
        return ClientActivityListResponse(
            items=[self._activity(record) for record in records], total=len(records)
        )

    def is_ready(self) -> bool:
        return self.repository.is_ready()


client_service = ClientService()
