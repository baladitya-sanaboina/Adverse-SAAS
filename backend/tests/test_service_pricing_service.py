import unittest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

from pydantic import ValidationError

from app.repositories.service_pricing_repository import (
    CompanyServiceRecord,
    PricingOverviewItemRecord,
    PricingSubjectRecord,
    ServiceCatalogConflict,
    ServiceCatalogReferenceError,
    ServiceDeleteBlocked,
    ServicePricingConflict,
    ServicePricingRecord,
)
from app.schemas.authentication import AuthContext
from app.schemas.service_pricing import (
    CompanyServiceCreate,
    CompanyServiceListFilters,
    CompanyServiceUpdate,
    PricingChangeRequest,
)
from app.services.authentication_service import AuthenticationError
from app.services.service_pricing_service import ServicePricingService


class FakeServicePricingRepository:
    def __init__(self) -> None:
        now = datetime.now(timezone.utc)
        self.company_id = uuid4()
        self.service_id = uuid4()
        self.client_id = uuid4()
        self.manager_id = uuid4()
        self.service_conflict: str | None = None
        self.delete_blocked = False
        self.pricing_reference: str | None = None
        self.pricing_conflict: str | None = None
        self.created_values: dict[str, object] | None = None
        self.updated_values: dict[str, object] | None = None
        self.list_filters: CompanyServiceListFilters | None = None
        self.services = (
            CompanyServiceRecord(
                self.service_id,
                self.company_id,
                "Reel",
                "REEL",
                "Short-form reel production service.",
                "PER_VIDEO",
                "COMMISSION_PER_DELIVERABLE",
                "ACTIVE",
                10,
                now,
                now,
                1,
                1,
                2,
                False,
            ),
        )
        self.client_subject = PricingSubjectRecord(self.client_id, "Client A", "CLI-001")
        self.manager_subject = PricingSubjectRecord(self.manager_id, "Manager A", "MGR-001")
        self.overview = (
            PricingOverviewItemRecord(
                self.service_id,
                "Reel",
                "REEL",
                "Short-form reel production service.",
                "ACTIVE",
                "PER_VIDEO",
                uuid4(),
                "CLIENT",
                "PER_VIDEO",
                Decimal("700.00"),
                "INR",
                "Priority client rate",
                now,
                None,
                uuid4(),
                "Company Admin",
                now,
                2,
            ),
        )
        self.history = (
            ServicePricingRecord(
                uuid4(),
                "CLIENT",
                "PER_VIDEO",
                Decimal("700.00"),
                "INR",
                "Priority client rate",
                now,
                None,
                uuid4(),
                "Company Admin",
                now,
                service_id=self.service_id,
                service_name="Reel",
                service_code="REEL",
                service_description="Short-form reel production service.",
                service_status="ACTIVE",
            ),
        )

    def service_code(self, name: str) -> str:
        return name.strip().upper().replace(" ", "_")

    def list_services(self, company_id, filters):
        self.list_filters = filters
        return self.services if company_id == self.company_id else (), len(self.services)

    def get_service(self, company_id, service_id):
        if company_id == self.company_id and service_id == self.service_id:
            return self.services[0]
        return None

    def create_service(self, company_id, actor_id, values):
        if self.service_conflict:
            raise ServiceCatalogConflict(self.service_conflict)
        self.created_values = values
        return CompanyServiceRecord(
            self.service_id,
            self.company_id,
            str(values["name"]),
            str(values["code"]),
            str(values.get("description") or ""),
            str(values["client_pricing_model"]),
            str(values["manager_pricing_model"]),
            str(values.get("status") or "ACTIVE"),
            int(values.get("sort_order") or 0),
            self.services[0].created_at,
            self.services[0].updated_at,
            0,
            0,
            0,
            True,
        )

    def update_service(self, company_id, actor_id, service_id, values):
        if self.service_conflict:
            raise ServiceCatalogConflict(self.service_conflict)
        if company_id != self.company_id or service_id != self.service_id:
            return None
        self.updated_values = values
        record = self.services[0]
        return CompanyServiceRecord(
            record.id,
            record.company_id,
            str(values.get("name", record.name)),
            record.code,
            str(values.get("description", record.description)),
            str(values.get("client_pricing_model", record.client_pricing_model)),
            str(values.get("manager_pricing_model", record.manager_pricing_model)),
            str(values.get("status", record.status)),
            int(values.get("sort_order", record.sort_order)),
            record.created_at,
            record.updated_at,
            record.active_client_rates,
            record.active_manager_rates,
            record.pricing_history_entries,
            record.safe_to_delete,
        )

    def delete_service(self, company_id, actor_id, service_id):
        if self.delete_blocked:
            raise ServiceDeleteBlocked
        return company_id == self.company_id and service_id == self.service_id

    def get_subject(self, company_id, scope, subject_id):
        if company_id != self.company_id:
            return None
        if scope == "CLIENT" and subject_id == self.client_id:
            return self.client_subject
        if scope == "MANAGER" and subject_id == self.manager_id:
            return self.manager_subject
        return None

    def list_pricing_overview(self, company_id, scope, subject_id):
        return self.overview if company_id == self.company_id else ()

    def list_pricing_history(self, company_id, scope, subject_id):
        return self.history if company_id == self.company_id else ()

    def set_pricing(self, company_id, actor_id, scope, subject_id, service_id, values):
        if self.pricing_reference:
            raise ServiceCatalogReferenceError(self.pricing_reference)
        if self.pricing_conflict:
            raise ServicePricingConflict(self.pricing_conflict)
        return ServicePricingRecord(
            uuid4(),
            scope,
            str(values.get("pricing_model") or "PER_VIDEO"),
            Decimal(str(values["amount"])),
            "INR",
            str(values.get("notes") or ""),
            values.get("effective_from") or self.services[0].updated_at,
            None,
            uuid4(),
            "Company Admin",
            self.services[0].updated_at,
        )

    def is_ready(self) -> bool:
        return True


class ServicePricingServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = FakeServicePricingRepository()
        self.service = ServicePricingService(self.repository)
        now = datetime.now(timezone.utc)
        self.context = AuthContext(
            user_id=uuid4(),
            role="COMPANY_ADMIN",
            company_id=self.repository.company_id,
            user_type="company",
            session_id=uuid4(),
            issued_at=now,
            expires_at=now,
        )

    @patch("app.services.service_pricing_service.validate_user_action_access", return_value=True)
    def test_company_admin_can_manage_services(self, _: object) -> None:
        listed = self.service.list_services(
            self.context, CompanyServiceListFilters(search="Reel", page=1, page_size=20)
        )
        self.assertEqual(listed.total, 1)
        self.assertEqual(
            self.repository.list_filters,
            CompanyServiceListFilters(search="Reel", page=1, page_size=20),
        )
        created = self.service.create_service(
            self.context,
            CompanyServiceCreate(
                name="Social Clips",
                description="Quick cutdowns",
                client_pricing_model="PER_VIDEO",
                manager_pricing_model="COMMISSION_PER_DELIVERABLE",
            ),
        )
        self.assertEqual(created.code, "SOCIAL_CLIPS")
        self.assertEqual(
            self.repository.created_values,
            {
                "name": "Social Clips",
                "description": "Quick cutdowns",
                "client_pricing_model": "PER_VIDEO",
                "manager_pricing_model": "COMMISSION_PER_DELIVERABLE",
                "status": "ACTIVE",
                "sort_order": 0,
                "code": "SOCIAL_CLIPS",
            },
        )
        updated = self.service.update_service(
            self.context,
            self.repository.service_id,
            CompanyServiceUpdate(status="INACTIVE", description="Paused"),
        )
        self.assertEqual(updated.status, "INACTIVE")
        self.assertEqual(
            self.repository.updated_values, {"description": "Paused", "status": "INACTIVE"}
        )
        detail = self.service.get_service(self.context, self.repository.service_id)
        self.assertEqual(detail.code, "REEL")
        self.service.delete_service(self.context, self.repository.service_id)

    @patch("app.services.service_pricing_service.validate_user_action_access", return_value=False)
    def test_missing_permission_is_forbidden(self, _: object) -> None:
        with self.assertRaises(AuthenticationError) as raised:
            self.service.list_services(self.context, CompanyServiceListFilters())
        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(raised.exception.code, "SETTINGS_VIEW_REQUIRED")

    @patch("app.services.service_pricing_service.validate_user_action_access", return_value=True)
    def test_pricing_overview_and_setters(self, _: object) -> None:
        overview = self.service.get_client_pricing(
            self.context, self.repository.client_id, include_history=True
        )
        self.assertEqual(overview.total_services, 1)
        self.assertEqual(overview.configured_services, 1)
        self.assertEqual(overview.subject.subtitle, "CLI-001")
        self.assertEqual(overview.items[0].history_count, 2)
        self.assertEqual(len(overview.items[0].history), 1)

        manager_rate = self.service.set_manager_pricing(
            self.context,
            self.repository.manager_id,
            self.repository.service_id,
            PricingChangeRequest(amount=Decimal("250.00"), notes="Manager payout"),
        )
        self.assertEqual(manager_rate.scope, "MANAGER")
        self.assertEqual(manager_rate.amount, Decimal("250.00"))

    @patch("app.services.service_pricing_service.validate_user_action_access", return_value=True)
    def test_conflicts_and_missing_resources_are_mapped(self, _: object) -> None:
        self.repository.service_conflict = "name"
        with self.assertRaises(AuthenticationError) as raised:
            self.service.create_service(
                self.context,
                CompanyServiceCreate(
                    name="Reel",
                    client_pricing_model="PER_VIDEO",
                    manager_pricing_model="COMMISSION_PER_DELIVERABLE",
                ),
            )
        self.assertEqual(raised.exception.code, "SERVICE_NAME_EXISTS")

        self.repository.delete_blocked = True
        with self.assertRaises(AuthenticationError) as raised:
            self.service.delete_service(self.context, self.repository.service_id)
        self.assertEqual(raised.exception.code, "SERVICE_DELETE_BLOCKED")

        self.repository.pricing_reference = "manager"
        with self.assertRaises(AuthenticationError) as raised:
            self.service.set_manager_pricing(
                self.context,
                uuid4(),
                self.repository.service_id,
                PricingChangeRequest(amount=Decimal("300.00")),
            )
        self.assertEqual(raised.exception.code, "MANAGER_NOT_FOUND")

        self.repository.pricing_reference = None
        self.repository.pricing_conflict = "service_inactive"
        with self.assertRaises(AuthenticationError) as raised:
            self.service.set_client_pricing(
                self.context,
                self.repository.client_id,
                self.repository.service_id,
                PricingChangeRequest(amount=Decimal("700.00")),
            )
        self.assertEqual(raised.exception.code, "SERVICE_INACTIVE")

    def test_schema_validation(self) -> None:
        with self.assertRaises(ValidationError):
            CompanyServiceCreate(
                name=" ",
                client_pricing_model="PER_VIDEO",
                manager_pricing_model="COMMISSION_PER_DELIVERABLE",
            )
        with self.assertRaises(ValidationError):
            CompanyServiceUpdate()


if __name__ == "__main__":
    unittest.main()
