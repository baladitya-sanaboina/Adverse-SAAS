import unittest
from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import ValidationError

from app.repositories.registration_repository import (
    ActorRecord,
    CompanyRecord,
    CreatedCompanyRecord,
    CreatedUserRecord,
)
from app.schemas.registration import (
    CreateClientRequest,
    CreateCompanyAdminRequest,
    CreateCompanyOnboardingRequest,
    CreateCompanyRequest,
    CreateDeveloperRequest,
    CreateEmployeeRequest,
)
from app.services.authentication_service import AuthenticationError
from app.services.password_service import verify_password
from app.services.registration_service import RegistrationError, RegistrationService

PLATFORM_OWNER_ID = UUID("11111111-1111-1111-1111-111111111111")
DEVELOPER_ID = UUID("22222222-2222-2222-2222-222222222222")
COMPANY_ADMIN_ID = UUID("33333333-3333-3333-3333-333333333333")
EMPLOYEE_ID = UUID("44444444-4444-4444-4444-444444444444")
COMPANY_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
SUSPENDED_COMPANY_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
STRONG_PASSWORD = "StrongPass!123"


class FakeRegistrationRepository:
    def __init__(self):
        self.actors = {
            PLATFORM_OWNER_ID: ActorRecord(PLATFORM_OWNER_ID, "PLATFORM_OWNER", "ACTIVE", None),
            DEVELOPER_ID: ActorRecord(DEVELOPER_ID, "DEVELOPER", "ACTIVE", None),
            COMPANY_ADMIN_ID: ActorRecord(COMPANY_ADMIN_ID, "COMPANY_ADMIN", "ACTIVE", COMPANY_ID),
            EMPLOYEE_ID: ActorRecord(EMPLOYEE_ID, "COMPANY_EMPLOYEE", "ACTIVE", COMPANY_ID),
        }
        self.companies = {
            COMPANY_ID: CompanyRecord(COMPANY_ID, "ACTIVE", "Starter"),
            SUSPENDED_COMPANY_ID: CompanyRecord(SUSPENDED_COMPANY_ID, "SUSPENDED", "Starter"),
        }
        self.emails: set[str] = set()
        self.password_hashes: dict[str, str] = {}
        self.audit_events: list[tuple[str, UUID, UUID | None, str | None]] = []

    def find_actor(self, actor_id: UUID):
        return self.actors.get(actor_id)

    def find_company(self, company_id: UUID):
        return self.companies.get(company_id)

    def email_exists(self, email: str) -> bool:
        return email in self.emails

    def list_users(self, *, role_code: str, company_id: UUID | None = None):
        return ()

    def list_companies(self, *, actor_id: UUID):
        return ()

    def create_user(
        self,
        *,
        actor_id: UUID,
        name: str,
        email: str,
        password_hash: str,
        role_code: str,
        company_id: UUID | None,
    ) -> CreatedUserRecord:
        user_id = uuid4()
        self.emails.add(email)
        self.password_hashes[email] = password_hash
        self.audit_events.append(("USER_CREATED", actor_id, company_id, role_code))
        return CreatedUserRecord(
            user_id,
            name,
            email,
            "ACTIVE",
            role_code,
            company_id,
            datetime.now(UTC),
        )

    def create_company(
        self,
        *,
        actor_id: UUID,
        name: str,
        code: str,
        subscription_plan: str,
        contact_email: str | None,
    ) -> CreatedCompanyRecord:
        company_id = uuid4()
        self.audit_events.append(("COMPANY_CREATED", actor_id, company_id, None))
        return CreatedCompanyRecord(
            company_id,
            name,
            code,
            subscription_plan,
            "ACTIVE",
            contact_email,
            datetime.now(UTC),
        )

    def create_company_with_admin(
        self,
        *,
        actor_id: UUID,
        company_name: str,
        company_code: str,
        subscription_plan: str,
        contact_email: str | None,
        admin_name: str,
        admin_email: str,
        admin_password_hash: str,
    ):
        company = self.create_company(
            actor_id=actor_id,
            name=company_name,
            code=company_code,
            subscription_plan=subscription_plan,
            contact_email=contact_email,
        )
        admin = self.create_user(
            actor_id=actor_id,
            name=admin_name,
            email=admin_email,
            password_hash=admin_password_hash,
            role_code="COMPANY_ADMIN",
            company_id=company.id,
        )
        return company, admin

    def foundation_is_ready(self) -> bool:
        return True


class FakeEnforcementService:
    def __init__(self):
        self.calls: list[tuple[UUID, str, int, UUID | None]] = []
        self.blocked_code: str | None = None

    def enforce_limit(
        self,
        company_id: UUID,
        resource_code: str,
        requested_increment: int = 1,
        actor_id: UUID | None = None,
    ) -> None:
        self.calls.append((company_id, resource_code, requested_increment, actor_id))
        if self.blocked_code == resource_code:
            raise AuthenticationError(
                403, "SUBSCRIPTION_LIMIT_REACHED", "Plan limit reached. Upgrade recommended."
            )


def user_payload(email: str) -> dict[str, object]:
    return {
        "name": "Registered User",
        "email": email,
        "password": STRONG_PASSWORD,
        "confirm_password": STRONG_PASSWORD,
    }


class RegistrationFoundationTests(unittest.TestCase):
    def setUp(self):
        self.repository = FakeRegistrationRepository()
        self.enforcement = FakeEnforcementService()
        self.service = RegistrationService(
            self.repository,
            enforcement_service=self.enforcement,  # type: ignore[arg-type]
        )

    def test_platform_owner_creates_developer_with_hashed_password_and_audit(self):
        created = self.service.create_developer(
            CreateDeveloperRequest(**user_payload("developer@example.com")), PLATFORM_OWNER_ID
        )
        encoded_hash = self.repository.password_hashes[created.email]
        self.assertEqual(created.role, "DEVELOPER")
        self.assertNotEqual(encoded_hash, STRONG_PASSWORD)
        self.assertTrue(verify_password(STRONG_PASSWORD, encoded_hash))
        self.assertEqual(self.repository.audit_events[0][0], "USER_CREATED")

    def test_developer_creates_company_and_company_admin(self):
        company, admin = self.service.onboard_company(
            CreateCompanyOnboardingRequest(
                company=CreateCompanyRequest(
                    name="Example Company",
                    code="EXAMPLE_CO",
                    subscription_plan="Starter",
                    contact_email="contact@example.com",
                ),
                admin=user_payload("admin@example.com"),
            ),
            DEVELOPER_ID,
        )
        self.assertEqual(company.status, "ACTIVE")
        self.assertEqual(admin.role, "COMPANY_ADMIN")

    def test_company_admin_creates_employee_and_client(self):
        employee = self.service.create_employee(
            CreateEmployeeRequest(
                **user_payload("employee@example.com"),
            ),
            COMPANY_ADMIN_ID,
            COMPANY_ID,
        )
        client = self.service.create_client(
            CreateClientRequest(
                **user_payload("client@example.com"),
            ),
            COMPANY_ADMIN_ID,
            COMPANY_ID,
        )
        self.assertEqual(employee.role, "COMPANY_EMPLOYEE")
        self.assertEqual(client.role, "COMPANY_CLIENT")
        self.assertEqual(
            [call[1] for call in self.enforcement.calls], ["MAX_EMPLOYEES", "MAX_CLIENTS"]
        )

    def test_employee_creation_is_blocked_when_plan_limit_is_reached(self):
        self.enforcement.blocked_code = "MAX_EMPLOYEES"
        with self.assertRaisesRegex(RegistrationError, "Upgrade recommended"):
            self.service.create_employee(
                CreateEmployeeRequest(**user_payload("limited@example.com")),
                COMPANY_ADMIN_ID,
                COMPANY_ID,
            )
        self.assertNotIn("limited@example.com", self.repository.emails)

    def test_employee_cannot_create_client(self):
        with self.assertRaisesRegex(RegistrationError, "cannot create"):
            self.service.create_client(
                CreateClientRequest(
                    **user_payload("client@example.com"),
                ),
                EMPLOYEE_ID,
                COMPANY_ID,
            )

    def test_duplicate_email_is_rejected(self):
        request = CreateDeveloperRequest(**user_payload("duplicate@example.com"))
        self.service.create_developer(request, PLATFORM_OWNER_ID)
        with self.assertRaisesRegex(RegistrationError, "already registered"):
            self.service.create_developer(request, PLATFORM_OWNER_ID)

    def test_suspended_company_is_rejected(self):
        with self.assertRaisesRegex(RegistrationError, "not active"):
            self.service.create_company_admin(
                CreateCompanyAdminRequest(
                    **user_payload("admin@example.com"),
                    company_id=SUSPENDED_COMPANY_ID,
                ),
                DEVELOPER_ID,
            )

    def test_invalid_email_weak_password_and_confirmation_are_rejected(self):
        invalid_payload = user_payload("not-an-email")
        with self.assertRaises(ValidationError):
            CreateDeveloperRequest(**invalid_payload)

        weak_payload = user_payload("valid@example.com")
        weak_payload.update(password="weakpassword", confirm_password="weakpassword")
        with self.assertRaises(ValidationError):
            CreateDeveloperRequest(**weak_payload)

        mismatch_payload = user_payload("valid@example.com")
        mismatch_payload["confirm_password"] = "DifferentPass!123"
        with self.assertRaises(ValidationError):
            CreateDeveloperRequest(**mismatch_payload)


if __name__ == "__main__":
    unittest.main()
