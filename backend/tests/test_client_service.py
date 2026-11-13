import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from uuid import UUID, uuid4

from pydantic import ValidationError

from app.repositories.client_repository import (
    ClientActivityRecord,
    ClientConflict,
    ClientContactRecord,
    ClientFeedbackRecord,
    ClientNoteRecord,
    ClientRecord,
    ClientReferenceError,
)
from app.schemas.authentication import AuthContext
from app.schemas.client import (
    ClientContactCreate,
    ClientContactUpdate,
    ClientCreate,
    ClientFeedbackCreate,
    ClientFeedbackUpdate,
    ClientListFilters,
    ClientNoteCreate,
    ClientNoteUpdate,
    ClientUpdate,
)
from app.schemas.service_pricing import (
    PricingOverviewResponse,
    PricingSubjectSummary,
    ServicePricingRecordResponse,
    SubjectServicePricingItemResponse,
)
from app.services.authentication_service import AuthenticationError
from app.services.client_service import ClientService


class FakePricingService:
    def get_pricing_overview_for_subject(
        self, company_id: UUID, scope: str, subject_id: UUID, *, include_history: bool
    ):
        self.company_id = company_id
        self.scope = scope
        self.subject_id = subject_id
        self.include_history = include_history
        current_rate = ServicePricingRecordResponse(
            id=uuid4(),
            scope="CLIENT",
            pricing_model="MONTHLY_FIXED",
            amount=30000,
            currency="INR",
            notes="Monthly client package",
            effective_from=datetime.now(UTC),
            effective_to=None,
            created_by_id=uuid4(),
            created_by_name="Company Admin",
            created_at=datetime.now(UTC),
        )
        return PricingOverviewResponse(
            scope="CLIENT",
            subject=PricingSubjectSummary(id=subject_id, name="ABC Pvt Ltd", subtitle="CLI-001"),
            items=[
                SubjectServicePricingItemResponse(
                    service_id=uuid4(),
                    service_name="Reel",
                    service_code="REEL",
                    service_description="Short-form reel production service.",
                    service_status="ACTIVE",
                    default_pricing_model="PER_VIDEO",
                    configured=True,
                    current_rate=current_rate,
                    history_count=1,
                    history=[],
                )
            ],
            total_services=1,
            configured_services=1,
            missing_services=0,
        )


class FakeClientRepository:
    def __init__(self) -> None:
        now = datetime.now(UTC)
        self.company_id = uuid4()
        self.other_company_id = uuid4()
        self.linked_user_id = uuid4()
        self.client_id = uuid4()
        self.contact_id = uuid4()
        self.other_contact_id = uuid4()
        self.note_id = uuid4()
        self.feedback_id = uuid4()
        self.conflict: str | None = None
        self.reference_missing = False
        self.updated_client: dict[str, object] | None = None
        self.updated_contact: dict[str, object] | None = None
        self.filters: ClientListFilters | None = None
        self.client = ClientRecord(
            self.client_id,
            self.company_id,
            "ABC Pvt Ltd",
            "CLI-001",
            "info@abc.example.com",
            "+91 9876543210",
            "https://abc.example.com/",
            "Hitech City",
            "Hyderabad",
            "Telangana",
            "India",
            "ACTIVE",
            now,
            now,
            "Raj Kumar",
            "raj@abc.example.com",
            "+91 9876543211",
            "CEO",
            self.linked_user_id,
            "Adverse Client",
            "adverseclient@gmail.com",
            "ACTIVE",
        )
        self.contacts = [
            ClientContactRecord(
                self.contact_id,
                self.client_id,
                "Raj",
                "Kumar",
                "raj@abc.example.com",
                "+91 9876543211",
                "CEO",
                True,
                "ACTIVE",
                now,
                now,
            ),
            ClientContactRecord(
                self.other_contact_id,
                self.client_id,
                "Priya",
                "Sharma",
                "priya@abc.example.com",
                None,
                "Finance Manager",
                False,
                "ACTIVE",
                now,
                now,
            ),
        ]
        self.notes = [
            ClientNoteRecord(
                self.note_id,
                self.client_id,
                uuid4(),
                "Company Admin",
                "Internal follow-up note",
                now,
                now,
            )
        ]
        self.feedback = [
            ClientFeedbackRecord(
                self.feedback_id,
                self.client_id,
                uuid4(),
                "Company Admin",
                "Client requested weekly updates",
                now,
                now,
            )
        ]
        self.activity: list[ClientActivityRecord] = []

    def list(
        self, company_id: UUID, filters: ClientListFilters
    ) -> tuple[tuple[ClientRecord, ...], int]:
        self.filters = filters
        records = (self.client,) if company_id == self.company_id else ()
        return records, len(records)

    def get(self, company_id: UUID, client_id: UUID) -> ClientRecord | None:
        if company_id == self.company_id and client_id == self.client_id:
            return self.client
        return None

    def get_for_user(self, company_id: UUID, user_id: UUID) -> ClientRecord | None:
        if company_id == self.company_id and user_id == self.linked_user_id:
            return self.client
        return None

    def create(self, company_id: UUID, values: dict[str, object]) -> ClientRecord:
        if self.conflict:
            raise ClientConflict(self.conflict)
        return self.client

    def update(
        self,
        company_id: UUID,
        client_id: UUID,
        actor_id: UUID,
        values: dict[str, object],
    ) -> ClientRecord | None:
        if self.conflict:
            raise ClientConflict(self.conflict)
        self.updated_client = values
        return self.get(company_id, client_id)

    def list_contacts(self, company_id: UUID, client_id: UUID) -> tuple[ClientContactRecord, ...]:
        if self.reference_missing or company_id != self.company_id or client_id != self.client_id:
            raise ClientReferenceError
        return tuple(self.contacts)

    def create_contact(
        self,
        company_id: UUID,
        client_id: UUID,
        actor_id: UUID,
        values: dict[str, object],
    ) -> ClientContactRecord:
        if self.reference_missing:
            raise ClientReferenceError
        if self.conflict:
            raise ClientConflict(self.conflict)
        if values.get("is_primary") is True:
            self.contacts = [replace(contact, is_primary=False) for contact in self.contacts]
        record = replace(
            self.contacts[0],
            id=uuid4(),
            first_name=str(values["first_name"]),
            is_primary=bool(values.get("is_primary", False)),
        )
        self.contacts.append(record)
        return record

    def update_contact(
        self,
        company_id: UUID,
        client_id: UUID,
        contact_id: UUID,
        actor_id: UUID,
        values: dict[str, object],
    ) -> ClientContactRecord | None:
        if self.reference_missing:
            raise ClientReferenceError
        if self.conflict:
            raise ClientConflict(self.conflict)
        self.updated_contact = values
        if company_id != self.company_id or client_id != self.client_id:
            raise ClientReferenceError
        current = next((contact for contact in self.contacts if contact.id == contact_id), None)
        if current is None:
            return None
        if values.get("is_primary") is True:
            self.contacts = [
                replace(contact, is_primary=contact.id == contact_id) for contact in self.contacts
            ]
            current = replace(current, is_primary=True)
        return current

    def list_notes(self, company_id: UUID, client_id: UUID) -> tuple[ClientNoteRecord, ...]:
        if self.reference_missing or company_id != self.company_id or client_id != self.client_id:
            raise ClientReferenceError
        return tuple(sorted(self.notes, key=lambda item: item.created_at, reverse=True))

    def create_note(
        self, company_id: UUID, client_id: UUID, actor_id: UUID, content: str
    ) -> ClientNoteRecord:
        if self.reference_missing or company_id != self.company_id or client_id != self.client_id:
            raise ClientReferenceError
        now = datetime.now(UTC)
        record = ClientNoteRecord(uuid4(), client_id, actor_id, "Company Admin", content, now, now)
        self.notes.append(record)
        self._append_activity(actor_id, "NOTE_ADDED", "An internal client note was added.")
        return record

    def update_note(
        self, company_id: UUID, client_id: UUID, note_id: UUID, actor_id: UUID, content: str
    ) -> ClientNoteRecord | None:
        if self.reference_missing or company_id != self.company_id or client_id != self.client_id:
            raise ClientReferenceError
        current = next((note for note in self.notes if note.id == note_id), None)
        if current is None:
            return None
        updated = replace(current, content=content, updated_at=datetime.now(UTC))
        self.notes = [updated if note.id == note_id else note for note in self.notes]
        self._append_activity(actor_id, "NOTE_UPDATED", "An internal client note was updated.")
        return updated

    def delete_note(self, company_id: UUID, client_id: UUID, note_id: UUID, actor_id: UUID) -> bool:
        if self.reference_missing or company_id != self.company_id or client_id != self.client_id:
            raise ClientReferenceError
        before = len(self.notes)
        self.notes = [note for note in self.notes if note.id != note_id]
        if len(self.notes) == before:
            return False
        self._append_activity(actor_id, "NOTE_DELETED", "An internal client note was deleted.")
        return True

    def list_feedback(self, company_id: UUID, client_id: UUID) -> tuple[ClientFeedbackRecord, ...]:
        if self.reference_missing or company_id != self.company_id or client_id != self.client_id:
            raise ClientReferenceError
        return tuple(sorted(self.feedback, key=lambda item: item.created_at, reverse=True))

    def create_feedback(
        self, company_id: UUID, client_id: UUID, actor_id: UUID, content: str
    ) -> ClientFeedbackRecord:
        if self.reference_missing or company_id != self.company_id or client_id != self.client_id:
            raise ClientReferenceError
        now = datetime.now(UTC)
        record = ClientFeedbackRecord(
            uuid4(), client_id, actor_id, "Company Admin", content, now, now
        )
        self.feedback.append(record)
        self._append_activity(actor_id, "FEEDBACK_ADDED", "Client feedback was added.")
        return record

    def update_feedback(
        self,
        company_id: UUID,
        client_id: UUID,
        feedback_id: UUID,
        actor_id: UUID,
        content: str,
    ) -> ClientFeedbackRecord | None:
        if self.reference_missing or company_id != self.company_id or client_id != self.client_id:
            raise ClientReferenceError
        current = next((item for item in self.feedback if item.id == feedback_id), None)
        if current is None:
            return None
        updated = replace(current, content=content, updated_at=datetime.now(UTC))
        self.feedback = [updated if item.id == feedback_id else item for item in self.feedback]
        self._append_activity(actor_id, "FEEDBACK_UPDATED", "Client feedback was updated.")
        return updated

    def list_activity(self, company_id: UUID, client_id: UUID) -> tuple[ClientActivityRecord, ...]:
        if self.reference_missing or company_id != self.company_id or client_id != self.client_id:
            raise ClientReferenceError
        return tuple(sorted(self.activity, key=lambda item: item.created_at, reverse=True))

    def _append_activity(self, actor_id: UUID, activity_type: str, description: str) -> None:
        self.activity.append(
            ClientActivityRecord(
                uuid4(),
                self.client_id,
                actor_id,
                "Company Admin",
                activity_type,
                description,
                datetime.now(UTC),
            )
        )

    def is_ready(self) -> bool:
        return True


class ClientServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = FakeClientRepository()
        self.pricing_service = FakePricingService()
        self.service = ClientService(self.repository, self.pricing_service)  # type: ignore[arg-type]
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
        self.request = ClientCreate(
            name=" ABC Pvt Ltd ",
            code="cli-001",
            email="INFO@ABC.EXAMPLE.COM",
            phone="+91 9876543210",
            website="https://abc.example.com",
            city=" Hyderabad ",
            state="Telangana",
            country="India",
        )

    @patch("app.services.client_service.validate_user_action_access", return_value=True)
    def test_create_list_get_and_update_client(self, _: object) -> None:
        self.assertEqual(self.request.name, "ABC Pvt Ltd")
        self.assertEqual(self.request.code, "CLI-001")
        self.assertEqual(self.request.email, "info@abc.example.com")
        self.assertEqual(
            self.service.create(self.context, self.request).company_id, self.context.company_id
        )

        listed = self.service.list(
            self.context, ClientListFilters(search="ABC", page=1, page_size=20)
        )
        self.assertEqual(listed.total, 1)
        self.assertEqual(listed.total_pages, 1)
        self.assertEqual(listed.items[0].primary_contact_name, "Raj Kumar")
        self.assertEqual(listed.items[0].primary_contact_email, "raj@abc.example.com")
        filters = self.repository.filters
        self.assertIsNotNone(filters)
        if filters is None:
            self.fail("Client list filters were not captured.")
        self.assertEqual(filters.search, "ABC")

        detail = self.service.get(self.context, self.repository.client_id)
        self.assertEqual(detail.code, "CLI-001")
        self.assertEqual(len(detail.contacts), 2)

        self.service.update(
            self.context,
            self.repository.client_id,
            ClientUpdate(code="cli-002", status="INACTIVE"),
        )
        self.assertEqual(self.repository.updated_client, {"code": "CLI-002", "status": "INACTIVE"})

    @patch("app.services.client_service.validate_user_action_access", return_value=True)
    def test_duplicate_client_code_returns_conflict(self, _: object) -> None:
        self.repository.conflict = "code"
        with self.assertRaises(AuthenticationError) as raised:
            self.service.create(self.context, self.request)
        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(raised.exception.code, "CLIENT_CODE_EXISTS")

    @patch("app.services.client_service.validate_user_action_access", return_value=True)
    def test_duplicate_client_email_returns_conflict(self, _: object) -> None:
        self.repository.conflict = "email"
        with self.assertRaises(AuthenticationError) as raised:
            self.service.create(self.context, self.request)
        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(raised.exception.code, "CLIENT_EMAIL_EXISTS")

    @patch("app.services.client_service.validate_user_action_access", return_value=True)
    def test_create_and_list_contacts(self, _: object) -> None:
        created = self.service.create_contact(
            self.context,
            self.repository.client_id,
            ClientContactCreate(
                first_name="Anil",
                email="ANIL@ABC.EXAMPLE.COM",
                designation="Operations",
                is_primary=True,
            ),
        )
        self.assertTrue(created.is_primary)
        contacts = self.service.list_contacts(self.context, self.repository.client_id)
        self.assertEqual(contacts.total, 3)
        self.assertEqual(sum(contact.is_primary for contact in contacts.items), 1)

    @patch("app.services.client_service.validate_user_action_access", return_value=True)
    def test_updating_primary_contact_keeps_only_one_primary(self, _: object) -> None:
        updated = self.service.update_contact(
            self.context,
            self.repository.client_id,
            self.repository.other_contact_id,
            ClientContactUpdate(is_primary=True),
        )
        self.assertTrue(updated.is_primary)
        self.assertEqual(sum(contact.is_primary for contact in self.repository.contacts), 1)
        self.assertEqual(self.repository.updated_contact, {"is_primary": True})

    @patch("app.services.client_service.validate_user_action_access", return_value=True)
    def test_duplicate_contact_email_returns_conflict(self, _: object) -> None:
        self.repository.conflict = "contact_email"
        with self.assertRaises(AuthenticationError) as raised:
            self.service.create_contact(
                self.context,
                self.repository.client_id,
                ClientContactCreate(first_name="Raj", email="raj@abc.example.com"),
            )
        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(raised.exception.code, "CLIENT_CONTACT_EMAIL_EXISTS")

    @patch("app.services.client_service.validate_user_action_access", return_value=True)
    def test_cross_tenant_client_and_contacts_are_not_found(self, _: object) -> None:
        foreign = self.context.model_copy(update={"company_id": self.repository.other_company_id})
        with self.assertRaises(AuthenticationError) as client_error:
            self.service.get(foreign, self.repository.client_id)
        self.assertEqual(client_error.exception.status_code, 404)

        with self.assertRaises(AuthenticationError) as contact_error:
            self.service.list_contacts(foreign, self.repository.client_id)
        self.assertEqual(contact_error.exception.status_code, 404)

    @patch("app.services.client_service.validate_user_action_access", return_value=True)
    def test_missing_client_or_contact_returns_not_found(self, _: object) -> None:
        self.repository.reference_missing = True
        with self.assertRaises(AuthenticationError) as client_error:
            self.service.create_contact(
                self.context, uuid4(), ClientContactCreate(first_name="Missing")
            )
        self.assertEqual(client_error.exception.code, "CLIENT_NOT_FOUND")

        self.repository.reference_missing = False
        with self.assertRaises(AuthenticationError) as contact_error:
            self.service.update_contact(
                self.context,
                self.repository.client_id,
                uuid4(),
                ClientContactUpdate(status="INACTIVE"),
            )
        self.assertEqual(contact_error.exception.code, "CLIENT_CONTACT_NOT_FOUND")

    @patch("app.services.client_service.validate_user_action_access", return_value=False)
    def test_missing_permission_is_forbidden(self, _: object) -> None:
        with self.assertRaises(AuthenticationError) as raised:
            self.service.list(self.context, ClientListFilters())
        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(raised.exception.code, "CLIENTS_VIEW_REQUIRED")

    @patch("app.services.client_service.validate_user_action_access")
    def test_company_role_scoping_uses_existing_client_permissions(self, access: object) -> None:
        def has_access(_user_id: str, role: str, module: str, action: str) -> bool:
            self.assertEqual(module, "CLIENTS")
            if role == "COMPANY_ADMIN":
                return True
            if role == "COMPANY_EMPLOYEE":
                return action == "VIEW"
            return False

        access.side_effect = has_access  # type: ignore[attr-defined]

        self.assertEqual(self.service.list(self.context, ClientListFilters()).total, 1)
        employee = self.context.model_copy(update={"role": "COMPANY_EMPLOYEE"})
        self.assertEqual(self.service.list(employee, ClientListFilters()).total, 1)
        self.assertEqual(
            self.service.list_feedback(employee, self.repository.client_id).total,
            1,
        )
        with self.assertRaises(AuthenticationError) as employee_create:
            self.service.create(employee, self.request)
        self.assertEqual(employee_create.exception.status_code, 403)
        self.assertEqual(employee_create.exception.code, "CLIENTS_CREATE_REQUIRED")

        client = self.context.model_copy(update={"role": "COMPANY_CLIENT"})
        with self.assertRaises(AuthenticationError) as client_view:
            self.service.list(client, ClientListFilters())
        self.assertEqual(client_view.exception.status_code, 403)
        self.assertEqual(client_view.exception.code, "CLIENTS_VIEW_REQUIRED")

    @patch("app.services.client_service.validate_user_action_access", return_value=True)
    def test_client_account_cannot_bypass_internal_history_with_a_grant(self, _: object) -> None:
        client = self.context.model_copy(update={"role": "COMPANY_CLIENT"})
        for operation in (
            lambda: self.service.list_notes(client, self.repository.client_id),
            lambda: self.service.list_activity(client, self.repository.client_id),
        ):
            with self.assertRaises(AuthenticationError) as raised:
                operation()
            self.assertEqual(raised.exception.status_code, 403)
            self.assertEqual(raised.exception.code, "CLIENT_HISTORY_INTERNAL_ONLY")

    def test_platform_context_is_forbidden(self) -> None:
        platform = self.context.model_copy(
            update={"role": "PLATFORM_OWNER", "company_id": None, "user_type": "platform"}
        )
        with self.assertRaises(AuthenticationError) as raised:
            self.service.list(platform, ClientListFilters())
        self.assertEqual(raised.exception.status_code, 403)

    def test_client_portal_dashboard_uses_linked_client_profile(self) -> None:
        now = datetime.now(UTC)
        client_context = AuthContext(
            user_id=self.repository.linked_user_id,
            role="COMPANY_CLIENT",
            company_id=self.repository.company_id,
            user_type="company",
            session_id=uuid4(),
            issued_at=now,
            expires_at=now + timedelta(minutes=30),
        )
        dashboard = self.service.get_portal_dashboard(client_context)
        self.assertEqual(dashboard.client.id, self.repository.client_id)
        self.assertEqual(dashboard.pricing.configured_services, 1)
        self.assertEqual(len(dashboard.packages), 1)
        self.assertFalse(dashboard.work.ready)
        self.assertFalse(dashboard.billing.ready)

    def test_schema_rejects_invalid_and_empty_updates(self) -> None:
        with self.assertRaises(ValidationError):
            ClientCreate(name="A", code="bad code")
        with self.assertRaises(ValidationError):
            ClientUpdate()
        with self.assertRaises(ValidationError):
            ClientContactCreate(first_name=" ")
        with self.assertRaises(ValidationError):
            ClientContactUpdate()

    @patch("app.services.client_service.validate_user_action_access", return_value=True)
    def test_notes_feedback_and_activity_flow(self, _: object) -> None:
        note = self.service.create_note(
            self.context, self.repository.client_id, ClientNoteCreate(content=" Call next Monday ")
        )
        self.assertEqual(note.content, "Call next Monday")
        updated_note = self.service.update_note(
            self.context,
            self.repository.client_id,
            note.id,
            ClientNoteUpdate(content="Call next Tuesday"),
        )
        self.assertEqual(updated_note.content, "Call next Tuesday")
        self.assertGreaterEqual(
            self.service.list_notes(self.context, self.repository.client_id).total, 2
        )

        feedback = self.service.create_feedback(
            self.context,
            self.repository.client_id,
            ClientFeedbackCreate(content="Needs a weekly status email"),
        )
        updated_feedback = self.service.update_feedback(
            self.context,
            self.repository.client_id,
            feedback.id,
            ClientFeedbackUpdate(content="Needs a Friday status email"),
        )
        self.assertEqual(updated_feedback.content, "Needs a Friday status email")
        self.assertGreaterEqual(
            self.service.list_feedback(self.context, self.repository.client_id).total, 2
        )
        self.service.delete_note(self.context, self.repository.client_id, note.id)
        activities = self.service.list_activity(self.context, self.repository.client_id)
        self.assertEqual(
            [item.type for item in activities.items],
            ["NOTE_DELETED", "FEEDBACK_UPDATED", "FEEDBACK_ADDED", "NOTE_UPDATED", "NOTE_ADDED"],
        )

    @patch("app.services.client_service.validate_user_action_access", return_value=True)
    def test_history_is_tenant_scoped_and_hidden_from_client_accounts(self, _: object) -> None:
        foreign = self.context.model_copy(update={"company_id": self.repository.other_company_id})
        with self.assertRaises(AuthenticationError) as tenant_error:
            self.service.list_notes(foreign, self.repository.client_id)
        self.assertEqual(tenant_error.exception.status_code, 404)

        client_account = self.context.model_copy(update={"role": "COMPANY_CLIENT"})
        with self.assertRaises(AuthenticationError) as role_error:
            self.service.list_notes(client_account, self.repository.client_id)
        self.assertEqual(role_error.exception.status_code, 403)
        self.assertEqual(role_error.exception.code, "CLIENT_HISTORY_INTERNAL_ONLY")

    @patch("app.services.client_service.validate_user_action_access", return_value=True)
    def test_missing_history_records_and_blank_content_are_rejected(self, _: object) -> None:
        with self.assertRaises(AuthenticationError) as note_error:
            self.service.update_note(
                self.context,
                self.repository.client_id,
                uuid4(),
                ClientNoteUpdate(content="Missing note"),
            )
        self.assertEqual(note_error.exception.code, "CLIENT_NOTE_NOT_FOUND")
        with self.assertRaises(AuthenticationError) as feedback_error:
            self.service.update_feedback(
                self.context,
                self.repository.client_id,
                uuid4(),
                ClientFeedbackUpdate(content="Missing feedback"),
            )
        self.assertEqual(feedback_error.exception.code, "CLIENT_FEEDBACK_NOT_FOUND")
        with self.assertRaises(ValidationError):
            ClientNoteCreate(content="   ")
        with self.assertRaises(ValidationError):
            ClientFeedbackCreate(content="")


if __name__ == "__main__":
    unittest.main()
