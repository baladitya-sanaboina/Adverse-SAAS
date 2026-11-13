from typing import cast
from uuid import UUID

from app.repositories.company_integrations_repository import (
    CompanyIntegrationsRepository,
    IntegrationRecord,
    WorkflowRecord,
)
from app.schemas.authentication import AuthContext
from app.schemas.company_integrations import (
    CompanyIntegrationListResponse,
    CompanyIntegrationResponse,
    IntegrationConfiguration,
    IntegrationProvider,
    IntegrationStatus,
    IntegrationUpdate,
    WorkflowSettingsResponse,
    WorkflowSettingsUpdate,
)
from app.services.authentication_service import AuthenticationError

PROVIDERS: tuple[IntegrationProvider, ...] = ("GOOGLE_DRIVE", "SLACK", "STRIPE")


class CompanyIntegrationsService:
    def __init__(self, repository: CompanyIntegrationsRepository | None = None):
        self.repository = repository or CompanyIntegrationsRepository()

    @staticmethod
    def _company(context: AuthContext) -> tuple[UUID, UUID]:
        if context.role != "COMPANY_ADMIN" or context.company_id is None:
            raise AuthenticationError(
                403, "COMPANY_ADMIN_REQUIRED", "Company Admin access is required."
            )
        return context.user_id, context.company_id

    @staticmethod
    def _integration(record: IntegrationRecord) -> CompanyIntegrationResponse:
        return CompanyIntegrationResponse(
            provider=cast(IntegrationProvider, record.provider),
            status=cast(IntegrationStatus, record.status),
            enabled=record.enabled,
            configuration=IntegrationConfiguration(**record.configuration),
            connected_at=record.connected_at,
            updated_at=record.updated_at,
        )

    @staticmethod
    def _empty(provider: IntegrationProvider) -> CompanyIntegrationResponse:
        return CompanyIntegrationResponse(
            provider=provider,
            status="NOT_CONFIGURED",
            enabled=False,
            configuration=IntegrationConfiguration(),
            connected_at=None,
            updated_at=None,
        )

    def list(self, context: AuthContext) -> CompanyIntegrationListResponse:
        _, company_id = self._company(context)
        records = {record.provider: record for record in self.repository.list(company_id)}
        return CompanyIntegrationListResponse(
            items=[
                (
                    self._integration(records[provider])
                    if provider in records
                    else self._empty(provider)
                )
                for provider in PROVIDERS
            ]
        )

    def get(
        self, context: AuthContext, provider: IntegrationProvider
    ) -> CompanyIntegrationResponse:
        _, company_id = self._company(context)
        record = self.repository.get(company_id, provider)
        return self._integration(record) if record else self._empty(provider)

    def update(
        self, context: AuthContext, provider: IntegrationProvider, request: IntegrationUpdate
    ) -> CompanyIntegrationResponse:
        actor_id, company_id = self._company(context)
        self._validate(provider, request.configuration)
        return self._integration(
            self.repository.upsert(
                actor_id, company_id, provider, request.enabled, request.configuration.model_dump()
            )
        )

    def disconnect(
        self, context: AuthContext, provider: IntegrationProvider
    ) -> CompanyIntegrationResponse:
        actor_id, company_id = self._company(context)
        record = self.repository.disconnect(actor_id, company_id, provider)
        if record is None:
            raise AuthenticationError(
                404, "INTEGRATION_NOT_FOUND", "Integration configuration was not found."
            )
        return self._integration(record)

    def workflow(self, context: AuthContext) -> WorkflowSettingsResponse:
        _, company_id = self._company(context)
        record = self.repository.workflow(company_id)
        return self._workflow(record) if record else WorkflowSettingsResponse()

    def update_workflow(
        self, context: AuthContext, request: WorkflowSettingsUpdate
    ) -> WorkflowSettingsResponse:
        actor_id, company_id = self._company(context)
        return self._workflow(
            self.repository.update_workflow(actor_id, company_id, request.model_dump())
        )

    @staticmethod
    def _workflow(record: WorkflowRecord) -> WorkflowSettingsResponse:
        return WorkflowSettingsResponse(**record.__dict__)

    @staticmethod
    def _validate(provider: IntegrationProvider, configuration: IntegrationConfiguration) -> None:
        allowed = {
            "GOOGLE_DRIVE": {"document_upload", "document_download"},
            "SLACK": {"project_notifications", "task_notifications", "important_alerts"},
            "STRIPE": {"billing_enabled"},
        }[provider]
        supplied = {key for key, value in configuration.model_dump().items() if value}
        if supplied - allowed:
            raise AuthenticationError(
                400,
                "INVALID_INTEGRATION_CONFIGURATION",
                f"Unsupported {provider.replace('_', ' ').title()} configuration option.",
            )

    def is_ready(self) -> bool:
        return self.repository.is_ready()


company_integrations_service = CompanyIntegrationsService()
