import unittest
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch
from uuid import UUID, uuid4

from pydantic import ValidationError

from app.repositories.crm_repository import (
    CrmConflict,
    CrmReferenceError,
    LeadRecord,
    OpportunityRecord,
)
from app.schemas.authentication import AuthContext
from app.schemas.crm import (
    LeadCreate,
    LeadListFilters,
    LeadUpdate,
    OpportunityCreate,
    OpportunityListFilters,
    OpportunityUpdate,
)
from app.services.authentication_service import AuthenticationError
from app.services.crm_service import CrmService


class FakeCrmRepository:
    def __init__(self) -> None:
        now = datetime.now(UTC)
        self.company_id = uuid4()
        self.other_company_id = uuid4()
        self.actor_id = uuid4()
        self.owner_id = uuid4()
        self.client_id = uuid4()
        self.lead_id = uuid4()
        self.opportunity_id = uuid4()
        self.reference: str | None = None
        self.conflict = False
        self.lead_filters: LeadListFilters | None = None
        self.opportunity_filters: OpportunityListFilters | None = None
        self.last_lead_values: dict[str, object] = {}
        self.last_opportunity_values: dict[str, object] = {}
        self.lead = LeadRecord(
            self.lead_id,
            self.company_id,
            self.client_id,
            self.owner_id,
            "Rahul Sales",
            "Raj Kumar",
            "ABC Technologies",
            "raj@abc.example.com",
            "+91 9876543210",
            "REFERRAL",
            "QUALIFIED",
            "Interested in website development.",
            now,
            now,
        )
        self.opportunity = OpportunityRecord(
            self.opportunity_id,
            self.company_id,
            self.client_id,
            "ABC Technologies",
            self.lead_id,
            self.owner_id,
            "Rahul Sales",
            "Website Development",
            "Corporate website implementation",
            Decimal("500000.00"),
            "INR",
            "PROPOSAL",
            "OPEN",
            date(2026, 9, 30),
            now,
            now,
        )

    def _raise_reference(self) -> None:
        if self.reference:
            raise CrmReferenceError(self.reference)

    def list_options(
        self, company_id: UUID
    ) -> tuple[list[tuple[UUID, str]], list[tuple[UUID, str]]]:
        if company_id != self.company_id:
            return [], []
        return [(self.owner_id, "Rahul Sales")], [(self.client_id, "ABC Technologies")]

    def create_lead(
        self, company_id: UUID, actor_id: UUID, values: dict[str, object]
    ) -> LeadRecord:
        self.last_lead_values = values
        self._raise_reference()
        if self.conflict:
            raise CrmConflict("email")
        return self.lead

    def list_leads(
        self, company_id: UUID, filters: LeadListFilters
    ) -> tuple[tuple[LeadRecord, ...], int]:
        self.lead_filters = filters
        records = (self.lead,) if company_id == self.company_id else ()
        return records, len(records)

    def get_lead(self, company_id: UUID, lead_id: UUID) -> LeadRecord | None:
        if company_id == self.company_id and lead_id == self.lead_id:
            return self.lead
        return None

    def update_lead(
        self,
        company_id: UUID,
        actor_id: UUID,
        lead_id: UUID,
        values: dict[str, object],
    ) -> LeadRecord | None:
        self._raise_reference()
        if self.conflict:
            raise CrmConflict("email")
        current = self.get_lead(company_id, lead_id)
        return replace(current, **values) if current else None

    def create_opportunity(
        self, company_id: UUID, actor_id: UUID, values: dict[str, object]
    ) -> OpportunityRecord:
        self.last_opportunity_values = values
        self._raise_reference()
        stage = str(values.get("stage", "NEW"))
        return replace(
            self.opportunity,
            stage=stage,
            status="CLOSED" if stage in {"WON", "LOST"} else "OPEN",
        )

    def list_opportunities(
        self, company_id: UUID, filters: OpportunityListFilters
    ) -> tuple[tuple[OpportunityRecord, ...], int]:
        self.opportunity_filters = filters
        records = (self.opportunity,) if company_id == self.company_id else ()
        return records, len(records)

    def get_opportunity(self, company_id: UUID, opportunity_id: UUID) -> OpportunityRecord | None:
        if company_id == self.company_id and opportunity_id == self.opportunity_id:
            return self.opportunity
        return None

    def update_opportunity(
        self,
        company_id: UUID,
        actor_id: UUID,
        opportunity_id: UUID,
        values: dict[str, object],
    ) -> OpportunityRecord | None:
        self._raise_reference()
        current = self.get_opportunity(company_id, opportunity_id)
        if current is None:
            return None
        stage = str(values.get("stage", current.stage))
        return replace(
            current,
            **values,
            status="CLOSED" if stage in {"WON", "LOST"} else "OPEN",
        )

    def is_ready(self) -> bool:
        return True


class CrmServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = FakeCrmRepository()
        self.service = CrmService(self.repository)  # type: ignore[arg-type]
        now = datetime.now(UTC)
        self.context = AuthContext(
            user_id=self.repository.actor_id,
            role="COMPANY_ADMIN",
            company_id=self.repository.company_id,
            user_type="company",
            session_id=uuid4(),
            issued_at=now,
            expires_at=now + timedelta(minutes=30),
        )
        self.lead_request = LeadCreate(
            name=" Raj Kumar ",
            company_name=" ABC Technologies ",
            email="RAJ@ABC.EXAMPLE.COM",
            phone="+91 9876543210",
            source="REFERRAL",
            owner_id=self.repository.owner_id,
            client_id=self.repository.client_id,
        )
        self.opportunity_request = OpportunityCreate(
            name=" Website Development ",
            client_id=self.repository.client_id,
            lead_id=self.repository.lead_id,
            owner_id=self.repository.owner_id,
            value=Decimal("500000"),
            currency="inr",
            stage="PROPOSAL",
            expected_close_date=date(2026, 9, 30),
        )

    @patch("app.services.crm_service.validate_user_action_access", return_value=True)
    def test_lead_create_list_get_and_update(self, _: object) -> None:
        self.assertEqual(self.lead_request.name, "Raj Kumar")
        self.assertEqual(self.lead_request.email, "raj@abc.example.com")
        created = self.service.create_lead(self.context, self.lead_request)
        self.assertEqual(created.company_id, self.repository.company_id)
        self.assertIsInstance(self.repository.last_lead_values["owner_id"], UUID)
        self.assertIsInstance(self.repository.last_lead_values["client_id"], UUID)

        listed = self.service.list_leads(
            self.context,
            LeadListFilters(search="ABC", status="QUALIFIED", source="REFERRAL"),
        )
        self.assertEqual(listed.total, 1)
        self.assertEqual(listed.items[0].owner_name, "Rahul Sales")
        self.assertEqual(
            self.service.get_lead(self.context, self.repository.lead_id).id, created.id
        )
        updated = self.service.update_lead(
            self.context, self.repository.lead_id, LeadUpdate(status="CONVERTED")
        )
        self.assertEqual(updated.status, "CONVERTED")

    @patch("app.services.crm_service.validate_user_action_access", return_value=True)
    def test_pipeline_options_are_tenant_scoped(self, _: object) -> None:
        options = self.service.options(self.context)
        self.assertEqual(options.owners[0].id, self.repository.owner_id)
        self.assertEqual(options.clients[0].id, self.repository.client_id)
        foreign = self.context.model_copy(update={"company_id": self.repository.other_company_id})
        foreign_options = self.service.options(foreign)
        self.assertEqual(foreign_options.owners, [])
        self.assertEqual(foreign_options.clients, [])

    @patch("app.services.crm_service.validate_user_action_access", return_value=True)
    def test_lead_to_opportunity_flow_and_derived_status(self, _: object) -> None:
        created = self.service.create_opportunity(self.context, self.opportunity_request)
        self.assertEqual(created.lead_id, self.repository.lead_id)
        self.assertEqual(created.client_id, self.repository.client_id)
        self.assertEqual(created.status, "OPEN")
        self.assertIsInstance(self.repository.last_opportunity_values["client_id"], UUID)
        self.assertIsInstance(self.repository.last_opportunity_values["lead_id"], UUID)
        self.assertIsInstance(self.repository.last_opportunity_values["owner_id"], UUID)
        self.assertIsInstance(self.repository.last_opportunity_values["value"], Decimal)
        self.assertIsInstance(self.repository.last_opportunity_values["expected_close_date"], date)

        listed = self.service.list_opportunities(
            self.context, OpportunityListFilters(stage="PROPOSAL")
        )
        self.assertEqual(listed.total, 1)
        self.assertEqual(listed.items[0].value, Decimal("500000.00"))
        updated = self.service.update_opportunity(
            self.context,
            self.repository.opportunity_id,
            OpportunityUpdate(stage="WON"),
        )
        self.assertEqual(updated.stage, "WON")
        self.assertEqual(updated.status, "CLOSED")

    @patch("app.services.crm_service.validate_user_action_access", return_value=True)
    def test_duplicate_lead_email_is_conflict(self, _: object) -> None:
        self.repository.conflict = True
        with self.assertRaises(AuthenticationError) as raised:
            self.service.create_lead(self.context, self.lead_request)
        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(raised.exception.code, "LEAD_EMAIL_EXISTS")

    @patch("app.services.crm_service.validate_user_action_access", return_value=True)
    def test_cross_tenant_records_are_not_found(self, _: object) -> None:
        foreign = self.context.model_copy(update={"company_id": self.repository.other_company_id})
        with self.assertRaises(AuthenticationError) as lead_error:
            self.service.get_lead(foreign, self.repository.lead_id)
        self.assertEqual(lead_error.exception.status_code, 404)
        with self.assertRaises(AuthenticationError) as opportunity_error:
            self.service.get_opportunity(foreign, self.repository.opportunity_id)
        self.assertEqual(opportunity_error.exception.status_code, 404)
        self.assertEqual(self.service.list_leads(foreign, LeadListFilters()).total, 0)

    @patch("app.services.crm_service.validate_user_action_access", return_value=True)
    def test_cross_tenant_relationships_are_rejected(self, _: object) -> None:
        for reference in ("owner", "client", "lead", "lead_client"):
            self.repository.reference = reference
            with self.assertRaises(AuthenticationError) as raised:
                self.service.create_opportunity(self.context, self.opportunity_request)
            self.assertEqual(raised.exception.status_code, 404)
            self.assertIn(reference.upper(), raised.exception.code)

    @patch("app.services.crm_service.validate_user_action_access", return_value=False)
    def test_missing_permission_is_forbidden(self, _: object) -> None:
        with self.assertRaises(AuthenticationError) as raised:
            self.service.list_leads(self.context, LeadListFilters())
        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(raised.exception.code, "CRM_VIEW_REQUIRED")

    @patch("app.services.crm_service.validate_user_action_access")
    def test_company_role_scoping_uses_existing_crm_permissions(self, access: object) -> None:
        def has_access(_user_id: str, role: str, module: str, action: str) -> bool:
            self.assertEqual(module, "CRM")
            if role == "COMPANY_ADMIN":
                return action in {"VIEW", "CREATE", "EDIT"}
            if role == "COMPANY_EMPLOYEE":
                return action == "VIEW"
            return False

        access.side_effect = has_access  # type: ignore[attr-defined]

        self.assertEqual(self.service.list_leads(self.context, LeadListFilters()).total, 1)
        employee = self.context.model_copy(update={"role": "COMPANY_EMPLOYEE"})
        self.assertEqual(self.service.list_leads(employee, LeadListFilters()).total, 1)
        with self.assertRaises(AuthenticationError) as employee_create:
            self.service.create_lead(employee, self.lead_request)
        self.assertEqual(employee_create.exception.status_code, 403)
        self.assertEqual(employee_create.exception.code, "CRM_CREATE_REQUIRED")

        client = self.context.model_copy(update={"role": "COMPANY_CLIENT"})
        with self.assertRaises(AuthenticationError) as client_view:
            self.service.list_opportunities(client, OpportunityListFilters())
        self.assertEqual(client_view.exception.status_code, 403)
        self.assertEqual(client_view.exception.code, "CRM_VIEW_REQUIRED")

    @patch("app.services.crm_service.validate_user_action_access", return_value=True)
    def test_platform_context_is_forbidden(self, _: object) -> None:
        platform = self.context.model_copy(
            update={"role": "PLATFORM_OWNER", "company_id": None, "user_type": "platform"}
        )
        with self.assertRaises(AuthenticationError) as raised:
            self.service.list_opportunities(platform, OpportunityListFilters())
        self.assertEqual(raised.exception.code, "COMPANY_CONTEXT_REQUIRED")

    def test_request_validation_and_normalization(self) -> None:
        self.assertEqual(self.opportunity_request.currency, "INR")
        with self.assertRaises(ValidationError):
            OpportunityCreate(
                name="Invalid",
                client_id=self.repository.client_id,
                owner_id=self.repository.owner_id,
                value=Decimal("-1"),
            )
        with self.assertRaises(ValidationError):
            LeadCreate(
                name="Lead",
                email="invalid-email",
                owner_id=self.repository.owner_id,
            )
        with self.assertRaises(ValidationError):
            LeadUpdate()
        with self.assertRaises(ValidationError):
            OpportunityUpdate()


if __name__ == "__main__":
    unittest.main()
