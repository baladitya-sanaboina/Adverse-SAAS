from app.core.constants import CompanyStatus, RoleCode
from app.repositories.registration_repository import RegistrationConflict, RegistrationRepository
from app.schemas.authentication import SignupRequest, SignupResponse
from app.services.authentication_service import AuthenticationError
from app.services.email_verification_service import (
    EmailVerificationService,
    email_verification_service,
)
from app.services.password_service import hash_password


class PublicSignupService:
    def __init__(
        self,
        repository: RegistrationRepository | None = None,
        verification_service: EmailVerificationService | None = None,
    ) -> None:
        self.repository = repository or RegistrationRepository()
        self.verification_service = verification_service or email_verification_service

    def signup(self, request: SignupRequest) -> SignupResponse:
        normalized_email = str(request.email).lower()
        if self.repository.email_exists(normalized_email):
            raise AuthenticationError(409, "EMAIL_EXISTS", "Email address is already registered.")

        password_hash = hash_password(request.password.get_secret_value())
        if request.role == "ADMIN":
            company_name = request.company_name.strip() if request.company_name else ""
            company_code = request.company_code.strip().upper() if request.company_code else ""
            try:
                company, user = self.repository.create_company_with_admin(
                    actor_id=None,
                    company_name=company_name,
                    company_code=company_code,
                    subscription_plan=request.subscription_plan,
                    contact_email=normalized_email,
                    admin_name=request.name.strip(),
                    admin_email=normalized_email,
                    admin_password_hash=password_hash,
                )
            except RegistrationConflict as error:
                self._raise_conflict(error)
            self.verification_service.start_for_created_user(user.email)
            return SignupResponse(email=user.email, role=request.role, company_code=company.code)

        company_code = request.company_code.strip().upper() if request.company_code else ""
        existing = self.repository.find_company_by_code(company_code)
        if existing is None:
            raise AuthenticationError(404, "COMPANY_NOT_FOUND", "Company code was not found.")
        if existing.status != CompanyStatus.ACTIVE.value:
            raise AuthenticationError(403, "COMPANY_INACTIVE", "Company is not active.")

        role_code = {
            "MANAGER": RoleCode.COMPANY_MANAGER.value,
            "EMPLOYEE": RoleCode.COMPANY_EMPLOYEE.value,
            "CLIENT": RoleCode.COMPANY_CLIENT.value,
        }[request.role]

        try:
            user = self.repository.create_user(
                actor_id=None,
                name=request.name.strip(),
                email=normalized_email,
                password_hash=password_hash,
                role_code=role_code,
                company_id=existing.id,
                phone_number=None,
            )
        except RegistrationConflict as error:
            self._raise_conflict(error)

        self.verification_service.start_for_created_user(user.email)
        return SignupResponse(email=user.email, role=request.role, company_code=existing.code)

    @staticmethod
    def _raise_conflict(error: RegistrationConflict) -> None:
        constraint = error.constraint_name or ""
        if constraint == "users_email_key":
            raise AuthenticationError(
                409, "EMAIL_EXISTS", "Email address is already registered."
            ) from error
        if constraint == "companies_code_key":
            raise AuthenticationError(
                409, "COMPANY_CODE_EXISTS", "Company code is already in use."
            ) from error
        if constraint == "companies_name_key":
            raise AuthenticationError(
                409, "COMPANY_NAME_EXISTS", "Company name is already in use."
            ) from error
        raise AuthenticationError(
            409, "REGISTRATION_CONFLICT", "Unable to complete signup."
        ) from error

    def is_ready(self) -> bool:
        return self.repository.foundation_is_ready()


public_signup_service = PublicSignupService()
