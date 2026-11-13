from uuid import UUID

from app.repositories.company_onboarding_repository import (
    CompanyOnboardingRepository,
    OnboardingConflict,
    OnboardingRecord,
)
from app.schemas.authentication import AuthContext
from app.schemas.company_onboarding import CompanyOnboardingRequest
from app.services.email_service import EmailService, email_service
from app.services.email_verification_service import email_verification_service
from app.services.password_service import hash_password
from app.services.registration_service import RegistrationError


class CompanyOnboardingService:
    def __init__(
        self,
        repository: CompanyOnboardingRepository | None = None,
        mailer: EmailService | None = None,
    ) -> None:
        self.repository = repository or CompanyOnboardingRepository()
        self.mailer = mailer or email_service

    def create(self, context: AuthContext, request: CompanyOnboardingRequest) -> OnboardingRecord:
        role = self.repository.actor_role(context.user_id)
        if role not in {"PLATFORM_OWNER", "DEVELOPER"}:
            raise RegistrationError(
                403, "ONBOARDING_FORBIDDEN", "Company onboarding access is required."
            )
        payload = request.model_dump(mode="json")
        payload["company"]["name"] = request.company.name.strip()
        payload["company"]["code"] = request.company.code.upper()
        payload["company"]["business_email"] = str(request.company.business_email).lower()
        payload["company"]["website"] = (
            str(request.company.website) if request.company.website else None
        )
        payload["admin"]["email"] = str(request.admin.email).lower()
        try:
            company_id = self.repository.create(
                actor_id=context.user_id,
                payload=payload,
                password_hash=hash_password(request.admin.password.get_secret_value()),
            )
        except LookupError as error:
            raise RegistrationError(
                404, "PLAN_NOT_FOUND", "The selected subscription plan was not found."
            ) from error
        except OnboardingConflict as error:
            mapping = {
                "companies_name_key": ("COMPANY_NAME_EXISTS", "Company name already exists."),
                "companies_code_key": ("COMPANY_CODE_EXISTS", "Company code already exists."),
                "companies_contact_email_key": (
                    "COMPANY_EMAIL_EXISTS",
                    "Business email already exists.",
                ),
                "users_email_key": ("EMAIL_EXISTS", "Admin email is already registered."),
            }
            code, detail = mapping.get(
                error.constraint or "",
                ("ONBOARDING_CONFLICT", "Company onboarding conflicts with existing data."),
            )
            raise RegistrationError(409, code, detail) from error
        sent = False
        try:
            self.mailer.send_company_welcome(
                payload["admin"]["email"],
                admin_name=f"{request.admin.first_name} {request.admin.last_name}".strip(),
                company_name=payload["company"]["name"],
                company_code=payload["company"]["code"],
            )
            email_verification_service.start_for_created_user(payload["admin"]["email"])
            sent = True
        finally:
            self.repository.finish_email(company_id, context.user_id, sent)
        record = self.repository.get(company_id)
        if record is None:
            raise RuntimeError("Created onboarding summary could not be loaded.")
        return record

    def get(self, context: AuthContext, company_id: UUID) -> OnboardingRecord:
        role = self.repository.actor_role(context.user_id)
        if role not in {"PLATFORM_OWNER", "DEVELOPER"}:
            raise RegistrationError(
                403, "ONBOARDING_FORBIDDEN", "Company onboarding access is required."
            )
        record = self.repository.get(company_id)
        if record is None:
            raise RegistrationError(
                404, "ONBOARDING_NOT_FOUND", "Company onboarding was not found."
            )
        return record

    def is_ready(self) -> bool:
        return self.repository.is_ready()


company_onboarding_service = CompanyOnboardingService()
