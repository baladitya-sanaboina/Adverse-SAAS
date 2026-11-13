import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from uuid import uuid4

from pydantic import ValidationError

from app.repositories.company_onboarding_repository import OnboardingConflict, OnboardingRecord
from app.schemas.authentication import AuthContext
from app.schemas.company_onboarding import CompanyOnboardingRequest
from app.services.company_onboarding_service import CompanyOnboardingService
from app.services.registration_service import RegistrationError


class FakeRepository:
    def __init__(self, role: str = "PLATFORM_OWNER", conflict: str | None = None) -> None:
        self.role = role
        self.conflict = conflict
        self.company_id = uuid4()
        self.finished: tuple[bool, str] | None = None

    def actor_role(self, _actor_id):  # type: ignore[no-untyped-def]
        return self.role

    def create(self, *, actor_id, payload, password_hash):  # type: ignore[no-untyped-def]
        if self.conflict:
            raise OnboardingConflict(self.conflict)
        self.payload = payload
        self.password_hash = password_hash
        return self.company_id

    def finish_email(self, company_id, actor_id, sent):  # type: ignore[no-untyped-def]
        self.finished = (sent, str(company_id))

    def get(self, company_id):  # type: ignore[no-untyped-def]
        now = datetime.now(UTC)
        return OnboardingRecord(
            id=uuid4(),
            status="COMPLETED",
            company={
                "id": company_id,
                "name": "Acme",
                "code": "ACME",
                "business_email": "hello@acme.example.com",
                "phone": None,
                "address": None,
                "website": None,
                "timezone": "UTC",
                "language": "en",
                "status": "ACTIVE",
            },
            subscription={
                "id": uuid4(),
                "name": "Starter",
                "code": "STARTER",
                "features": {"CRM": True},
                "limits": {"MAX_EMPLOYEES": 5},
            },
            admin={
                "id": uuid4(),
                "name": "Asha Rao",
                "email": "asha@acme.example.com",
                "phone": None,
                "role": "COMPANY_ADMIN",
                "status": "PENDING_VERIFICATION",
            },
            initialization={
                "company_created": True,
                "subscription_assigned": True,
                "admin_created": True,
                "tenant_initialized": True,
                "defaults_seeded": True,
                "welcome_email": "SENT",
            },
            started_at=now,
            completed_at=now,
            audit_trail=[],
        )

    def is_ready(self):  # type: ignore[no-untyped-def]
        return True


class FakeMailer:
    def __init__(self) -> None:
        self.sent_to = ""

    def send_company_welcome(self, email, **_kwargs):  # type: ignore[no-untyped-def]
        self.sent_to = email


def context() -> AuthContext:
    now = datetime.now(UTC)
    return AuthContext(
        user_id=uuid4(),
        role="PLATFORM_OWNER",
        company_id=None,
        user_type="platform",
        session_id=uuid4(),
        issued_at=now,
        expires_at=now + timedelta(minutes=30),
    )


def request() -> CompanyOnboardingRequest:
    return CompanyOnboardingRequest.model_validate(
        {
            "company": {
                "name": "Acme",
                "code": "ACME",
                "business_email": "hello@acme.example.com",
                "timezone": "UTC",
                "language": "en",
            },
            "subscription_plan_id": str(uuid4()),
            "admin": {
                "first_name": "Asha",
                "last_name": "Rao",
                "email": "asha@acme.example.com",
                "password": "StrongPass!123",
                "confirm_password": "StrongPass!123",
            },
        }
    )


class CompanyOnboardingTests(unittest.TestCase):
    @patch(
        "app.services.company_onboarding_service.email_verification_service.start_for_created_user"
    )
    def test_complete_onboarding_hashes_password_and_tracks_email(self, verification) -> None:  # type: ignore[no-untyped-def]
        repository, mailer = FakeRepository(), FakeMailer()
        service = CompanyOnboardingService(repository, mailer)  # type: ignore[arg-type]
        result = service.create(context(), request())
        self.assertEqual(result.status, "COMPLETED")
        self.assertNotEqual(repository.password_hash, "StrongPass!123")
        self.assertEqual(mailer.sent_to, "asha@acme.example.com")
        self.assertEqual(repository.finished, (True, str(repository.company_id)))
        verification.assert_called_once_with("asha@acme.example.com")

    def test_unauthorized_role_and_duplicate_name_are_rejected(self) -> None:
        with self.assertRaises(RegistrationError) as forbidden:
            CompanyOnboardingService(FakeRepository("COMPANY_ADMIN"), FakeMailer()).create(
                context(), request()
            )  # type: ignore[arg-type]
        self.assertEqual(forbidden.exception.status_code, 403)
        with self.assertRaises(RegistrationError) as duplicate:
            CompanyOnboardingService(
                FakeRepository(conflict="companies_name_key"), FakeMailer()
            ).create(
                context(), request()
            )  # type: ignore[arg-type]
        self.assertEqual(duplicate.exception.code, "COMPANY_NAME_EXISTS")

    def test_password_strength_and_confirmation_are_validated(self) -> None:
        payload = request().model_dump(mode="json")
        payload["admin"]["password"] = "weak-password"
        payload["admin"]["confirm_password"] = "different-pass"
        with self.assertRaises(ValidationError):
            CompanyOnboardingRequest.model_validate(payload)
