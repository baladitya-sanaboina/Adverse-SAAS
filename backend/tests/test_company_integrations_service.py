import unittest
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from app.repositories.company_integrations_repository import IntegrationRecord, WorkflowRecord
from app.schemas.authentication import AuthContext
from app.schemas.company_integrations import (
    IntegrationConfiguration,
    IntegrationUpdate,
    WorkflowSettingsUpdate,
)
from app.services.authentication_service import AuthenticationError
from app.services.company_integrations_service import CompanyIntegrationsService


class FakeIntegrationsRepository:
    def __init__(self) -> None:
        self.company_id = uuid4()
        self.integrations: dict[tuple[UUID, str], IntegrationRecord] = {}
        self.workflows: dict[UUID, WorkflowRecord] = {}

    def list(self, company_id: UUID):
        return tuple(
            record
            for (tenant_id, _), record in self.integrations.items()
            if tenant_id == company_id
        )

    def get(self, company_id: UUID, provider: str):
        return self.integrations.get((company_id, provider))

    def upsert(
        self,
        actor_id: UUID,
        company_id: UUID,
        provider: str,
        enabled: bool,
        configuration: dict[str, bool],
    ):
        now = datetime.now(UTC)
        record = IntegrationRecord(
            provider, "CONFIGURED" if enabled else "DISCONNECTED", enabled, configuration, None, now
        )
        self.integrations[(company_id, provider)] = record
        return record

    def disconnect(self, actor_id: UUID, company_id: UUID, provider: str):
        record = self.get(company_id, provider)
        if record is None:
            return None
        disconnected = IntegrationRecord(
            provider, "DISCONNECTED", False, record.configuration, None, datetime.now(UTC)
        )
        self.integrations[(company_id, provider)] = disconnected
        return disconnected

    def workflow(self, company_id: UUID):
        return self.workflows.get(company_id)

    def update_workflow(self, actor_id: UUID, company_id: UUID, values: dict[str, bool]):
        record = WorkflowRecord(**values, updated_at=datetime.now(UTC))
        self.workflows[company_id] = record
        return record

    def is_ready(self):
        return True


class CompanyIntegrationsServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = FakeIntegrationsRepository()
        self.service = CompanyIntegrationsService(self.repository)
        now = datetime.now(UTC)
        self.context = AuthContext(
            user_id=uuid4(),
            role="COMPANY_ADMIN",
            company_id=self.repository.company_id,
            user_type="company",
            session_id=uuid4(),
            issued_at=now,
            expires_at=now + timedelta(minutes=30),
        )

    def test_list_returns_supported_company_scoped_providers(self) -> None:
        response = self.service.list(self.context)
        self.assertEqual(
            [item.provider for item in response.items], ["GOOGLE_DRIVE", "SLACK", "STRIPE"]
        )
        self.assertTrue(all(item.status == "NOT_CONFIGURED" for item in response.items))

    def test_update_and_get_persist_non_secret_configuration(self) -> None:
        updated = self.service.update(
            self.context,
            "SLACK",
            IntegrationUpdate(
                enabled=True,
                configuration=IntegrationConfiguration(project_notifications=True),
            ),
        )
        self.assertEqual(updated.status, "CONFIGURED")
        self.assertTrue(self.service.get(self.context, "SLACK").configuration.project_notifications)

    def test_provider_rejects_configuration_from_another_provider(self) -> None:
        with self.assertRaises(AuthenticationError) as raised:
            self.service.update(
                self.context,
                "STRIPE",
                IntegrationUpdate(configuration=IntegrationConfiguration(document_upload=True)),
            )
        self.assertEqual(raised.exception.status_code, 400)

    def test_workflow_settings_persist_per_tenant(self) -> None:
        updated = self.service.update_workflow(
            self.context,
            WorkflowSettingsUpdate(approval_flow=True, client_notifications=False),
        )
        self.assertTrue(updated.approval_flow)
        self.assertFalse(self.service.workflow(self.context).client_notifications)
        other = self.context.model_copy(update={"company_id": uuid4()})
        self.assertFalse(self.service.workflow(other).approval_flow)

    def test_non_company_admin_is_forbidden(self) -> None:
        employee = self.context.model_copy(update={"role": "COMPANY_EMPLOYEE"})
        with self.assertRaises(AuthenticationError) as raised:
            self.service.list(employee)
        self.assertEqual(raised.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
