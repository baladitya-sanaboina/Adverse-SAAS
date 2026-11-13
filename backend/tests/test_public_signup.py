import unittest
from uuid import uuid4

from app.repositories.registration_repository import (
    CompanyLookupRecord,
    CreatedCompanyRecord,
    CreatedUserRecord,
    RegistrationConflict,
)
from app.schemas.authentication import SignupRequest
from app.services.authentication_service import AuthenticationError
from app.services.public_signup_service import PublicSignupService


class FakeVerificationService:
    def __init__(self):
        self.emails: list[str] = []

    def start_for_created_user(self, email: str) -> None:
        self.emails.append(email)


class FakeRegistrationRepository:
    def __init__(self):
        self.company = CompanyLookupRecord(uuid4(), "Acme Ops", "ACME_OPS", "ACTIVE", "Starter")
        self.email_taken = False
        self.created_members: list[dict[str, object]] = []
        self.created_admins: list[dict[str, object]] = []

    def email_exists(self, email: str) -> bool:
        return self.email_taken

    def create_company_with_admin(self, **kwargs):
        self.created_admins.append(kwargs)
        company = CreatedCompanyRecord(
            id=uuid4(),
            name=kwargs["company_name"],
            code=kwargs["company_code"],
            subscription_plan=kwargs["subscription_plan"],
            status="ACTIVE",
            contact_email=kwargs["contact_email"],
            created_at=None,
        )
        user = CreatedUserRecord(
            id=uuid4(),
            name=kwargs["admin_name"],
            email=kwargs["admin_email"],
            status="PENDING_VERIFICATION",
            role="COMPANY_ADMIN",
            company_id=company.id,
            created_at=None,
        )
        return company, user

    def find_company_by_code(self, code: str):
        return self.company if code == self.company.code else None

    def create_user(self, **kwargs):
        self.created_members.append(kwargs)
        return CreatedUserRecord(
            id=uuid4(),
            name=kwargs["name"],
            email=kwargs["email"],
            status="PENDING_VERIFICATION",
            role=kwargs["role_code"],
            company_id=kwargs["company_id"],
            created_at=None,
        )

    def foundation_is_ready(self):
        return True


class PublicSignupTests(unittest.TestCase):
    def setUp(self):
        self.repository = FakeRegistrationRepository()
        self.verification = FakeVerificationService()
        self.service = PublicSignupService(self.repository, self.verification)

    def test_admin_signup_creates_company_admin_and_triggers_verification(self):
        response = self.service.signup(
            SignupRequest(
                role="ADMIN",
                name="Asha Rao",
                email="admin@example.com",
                password="StrongPass!123",
                confirm_password="StrongPass!123",
                company_name="Acme Ops",
                company_code="ACME_OPS",
            )
        )
        self.assertEqual(response.role, "ADMIN")
        self.assertEqual(self.verification.emails, ["admin@example.com"])
        self.assertEqual(self.repository.created_admins[0]["company_code"], "ACME_OPS")

    def test_member_signup_joins_existing_company_with_role_mapping(self):
        response = self.service.signup(
            SignupRequest(
                role="MANAGER",
                name="Nikhil Varma",
                email="manager@example.com",
                password="StrongPass!123",
                confirm_password="StrongPass!123",
                company_code="ACME_OPS",
            )
        )
        self.assertEqual(response.company_code, "ACME_OPS")
        self.assertEqual(self.repository.created_members[0]["role_code"], "COMPANY_MANAGER")
        self.assertEqual(self.verification.emails, ["manager@example.com"])

    def test_unknown_company_code_is_rejected(self):
        with self.assertRaises(AuthenticationError) as context:
            self.service.signup(
                SignupRequest(
                    role="EMPLOYEE",
                    name="Priya",
                    email="priya@example.com",
                    password="StrongPass!123",
                    confirm_password="StrongPass!123",
                    company_code="UNKNOWN_CO",
                )
            )
        self.assertEqual(context.exception.code, "COMPANY_NOT_FOUND")

    def test_duplicate_email_is_rejected_before_creation(self):
        self.repository.email_taken = True
        with self.assertRaises(AuthenticationError) as context:
            self.service.signup(
                SignupRequest(
                    role="CLIENT",
                    name="Client User",
                    email="client@example.com",
                    password="StrongPass!123",
                    confirm_password="StrongPass!123",
                    company_code="ACME_OPS",
                )
            )
        self.assertEqual(context.exception.code, "EMAIL_EXISTS")

    def test_conflicts_are_mapped_to_user_facing_errors(self):
        class ConflictRepository(FakeRegistrationRepository):
            def create_company_with_admin(self, **kwargs):
                raise RegistrationConflict("companies_code_key")

        service = PublicSignupService(ConflictRepository(), self.verification)
        with self.assertRaises(AuthenticationError) as context:
            service.signup(
                SignupRequest(
                    role="ADMIN",
                    name="Asha Rao",
                    email="admin@example.com",
                    password="StrongPass!123",
                    confirm_password="StrongPass!123",
                    company_name="Acme Ops",
                    company_code="ACME_OPS",
                )
            )
        self.assertEqual(context.exception.code, "COMPANY_CODE_EXISTS")


if __name__ == "__main__":
    unittest.main()
