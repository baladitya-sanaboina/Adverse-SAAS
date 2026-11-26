from typing import Protocol
from uuid import UUID

from app.core.constants import CompanyStatus, RoleCode, UserStatus
from app.core.settings import settings
from app.repositories.registration_repository import (
    ActorRecord,
    CompanyRecord,
    CreatedCompanyRecord,
    CreatedUserRecord,
    RegistrationConflict,
    RegistrationRepository,
)
from app.schemas.registration import (
    CompanyUserRegistrationRequest,
    CreateClientRequest,
    CreateCompanyAdminRequest,
    CreateCompanyOnboardingRequest,
    CreateCompanyRequest,
    CreateDeveloperRequest,
    CreateEmployeeRequest,
)
from app.services.authentication_service import AuthenticationError
from app.services.email_verification_service import (
    EmailVerificationService,
    email_verification_service,
)
from app.services.password_service import hash_password
from app.services.subscription_enforcement_service import (
    SubscriptionEnforcementService,
    subscription_enforcement_service,
)


class RegistrationRepositoryProtocol(Protocol):
    def find_actor(self, actor_id: UUID) -> ActorRecord | None: ...

    def find_company(self, company_id: UUID) -> CompanyRecord | None: ...

    def email_exists(self, email: str) -> bool: ...

    def list_users(
        self, *, role_code: str, company_id: UUID | None = None
    ) -> tuple[CreatedUserRecord, ...]: ...

    def list_companies(self, *, actor_id: UUID) -> tuple[CreatedCompanyRecord, ...]: ...

    def create_user(
        self,
        *,
        actor_id: UUID,
        name: str,
        email: str,
        password_hash: str,
        role_code: str,
        company_id: UUID | None,
        phone_number: str | None,
    ) -> CreatedUserRecord: ...

    def create_company(
        self,
        *,
        actor_id: UUID,
        name: str,
        code: str,
        subscription_plan: str,
        contact_email: str | None,
    ) -> CreatedCompanyRecord: ...

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
    ) -> tuple[CreatedCompanyRecord, CreatedUserRecord]: ...

    def foundation_is_ready(self) -> bool: ...


class RegistrationError(Exception):
    def __init__(self, status_code: int, code: str, detail: str):
        self.status_code = status_code
        self.code = code
        self.detail = detail
        super().__init__(detail)


class RegistrationService:
    def __init__(
        self,
        repository: RegistrationRepositoryProtocol | None = None,
        verification_service: EmailVerificationService | None = None,
        enforcement_service: SubscriptionEnforcementService | None = None,
    ):
        self.repository = repository or RegistrationRepository()
        self.verification_service = verification_service or (
            email_verification_service if repository is None else None
        )
        self.enforcement_service = enforcement_service or (
            subscription_enforcement_service if repository is None else None
        )

    def create_developer(
        self, request: CreateDeveloperRequest, actor_id: UUID
    ) -> CreatedUserRecord:
        actor = self._require_actor(actor_id, RoleCode.PLATFORM_OWNER)
        return self._create_user(request, actor, RoleCode.DEVELOPER, company_id=None)

    def list_developers(self, actor_id: UUID) -> tuple[CreatedUserRecord, ...]:
        self._require_actor(actor_id, RoleCode.PLATFORM_OWNER)
        return self.repository.list_users(role_code=RoleCode.DEVELOPER.value)

    def list_companies(self, actor_id: UUID) -> tuple[CreatedCompanyRecord, ...]:
        actor = self._require_actor(actor_id, RoleCode.DEVELOPER)
        return self.repository.list_companies(actor_id=actor.id)

    def list_employees(self, actor_id: UUID, company_id: UUID) -> tuple[CreatedUserRecord, ...]:
        self._require_company_admin(actor_id, company_id)
        employees = self.repository.list_users(
            role_code=RoleCode.COMPANY_EMPLOYEE.value, company_id=company_id
        )
        managers = self.repository.list_users(
            role_code=RoleCode.COMPANY_MANAGER.value, company_id=company_id
        )
        return tuple(
            sorted((*employees, *managers), key=lambda user: user.created_at, reverse=True)
        )

    def list_clients(self, actor_id: UUID, company_id: UUID) -> tuple[CreatedUserRecord, ...]:
        self._require_company_admin(actor_id, company_id)
        return self.repository.list_users(
            role_code=RoleCode.COMPANY_CLIENT.value, company_id=company_id
        )

    def onboard_company(
        self, request: CreateCompanyOnboardingRequest, actor_id: UUID
    ) -> tuple[CreatedCompanyRecord, CreatedUserRecord]:
        actor = self._require_actor(actor_id, RoleCode.DEVELOPER)
        admin_email = str(request.admin.email).lower()
        if self.repository.email_exists(admin_email):
            raise RegistrationError(409, "EMAIL_EXISTS", "Email address is already registered.")
        try:
            company, admin = self.repository.create_company_with_admin(
                actor_id=actor.id,
                company_name=request.company.name.strip(),
                company_code=request.company.code.upper(),
                subscription_plan=request.company.subscription_plan.strip(),
                contact_email=(
                    str(request.company.contact_email).lower()
                    if request.company.contact_email
                    else None
                ),
                admin_name=request.admin.name.strip(),
                admin_email=admin_email,
                admin_password_hash=hash_password(request.admin.password.get_secret_value()),
            )
            self._start_verification(admin.email)
            return company, admin
        except RegistrationConflict as error:
            if error.constraint_name == "companies_code_key":
                raise RegistrationError(
                    409, "COMPANY_CODE_EXISTS", "Company code already exists."
                ) from error
            if error.constraint_name == "companies_contact_email_key":
                raise RegistrationError(
                    409,
                    "COMPANY_EMAIL_EXISTS",
                    "Company contact email is already registered.",
                ) from error
            if error.constraint_name == "users_email_key":
                raise RegistrationError(
                    409, "EMAIL_EXISTS", "Email address is already registered."
                ) from error
            raise RegistrationError(
                409, "REGISTRATION_CONFLICT", "Company onboarding already exists."
            ) from error

    def create_company(self, request: CreateCompanyRequest, actor_id: UUID) -> CreatedCompanyRecord:
        actor = self._require_actor(actor_id, RoleCode.DEVELOPER)
        try:
            return self.repository.create_company(
                actor_id=actor.id,
                name=request.name.strip(),
                code=request.code.upper(),
                subscription_plan=request.subscription_plan.strip(),
                contact_email=str(request.contact_email).lower() if request.contact_email else None,
            )
        except RegistrationConflict as error:
            if error.constraint_name == "companies_code_key":
                raise RegistrationError(
                    409, "COMPANY_CODE_EXISTS", "Company code already exists."
                ) from error
            if error.constraint_name == "companies_contact_email_key":
                raise RegistrationError(
                    409,
                    "COMPANY_EMAIL_EXISTS",
                    "Company contact email is already registered.",
                ) from error
            raise RegistrationError(
                409, "REGISTRATION_CONFLICT", "Company already exists."
            ) from error

    def create_company_admin(
        self, request: CreateCompanyAdminRequest, actor_id: UUID
    ) -> CreatedUserRecord:
        actor = self._require_actor(actor_id, RoleCode.DEVELOPER)
        company = self._require_active_company(request.company_id)
        self._require_subscription_capacity(company)
        return self._create_user(request, actor, RoleCode.COMPANY_ADMIN, company.id)

    def create_employee(
        self, request: CreateEmployeeRequest, actor_id: UUID, company_id: UUID
    ) -> CreatedUserRecord:
        actor = self._require_company_admin(actor_id, company_id)
        company = self._require_active_company(company_id)
        self._require_subscription_capacity(company)
        self._enforce_limit(company.id, "MAX_EMPLOYEES", actor.id)
        self._require_internal_login(str(request.email))
        return self._create_user(request, actor, RoleCode.COMPANY_EMPLOYEE, company.id)

    def create_client(
        self, request: CreateClientRequest, actor_id: UUID, company_id: UUID
    ) -> CreatedUserRecord:
        actor = self._require_company_admin(actor_id, company_id)
        company = self._require_active_company(company_id)
        self._require_subscription_capacity(company)
        self._enforce_limit(company.id, "MAX_CLIENTS", actor.id)
        self._require_internal_login(str(request.email))
        return self._create_user(request, actor, RoleCode.COMPANY_CLIENT, company.id)

    def is_ready(self) -> bool:
        return self.repository.foundation_is_ready()

    def _create_user(
        self,
        request: CreateDeveloperRequest | CompanyUserRegistrationRequest,
        actor: ActorRecord,
        role: RoleCode,
        company_id: UUID | None,
    ) -> CreatedUserRecord:
        normalized_email = str(request.email).lower()
        phone_number = (
            request.phone_number.strip()
            if isinstance(request, CompanyUserRegistrationRequest) and request.phone_number
            else None
        )
        if self.repository.email_exists(normalized_email):
            raise RegistrationError(409, "EMAIL_EXISTS", "Email address is already registered.")
        try:
            created = self.repository.create_user(
                actor_id=actor.id,
                name=request.name.strip(),
                email=normalized_email,
                password_hash=hash_password(request.password.get_secret_value()),
                role_code=role.value,
                company_id=company_id,
                phone_number=phone_number,
            )
            self._start_verification(created.email)
            return created
        except RegistrationConflict as error:
            if error.constraint_name == "users_email_key":
                raise RegistrationError(
                    409, "EMAIL_EXISTS", "Email address is already registered."
                ) from error
            raise RegistrationError(409, "REGISTRATION_CONFLICT", "User already exists.") from error

    @staticmethod
    def _require_internal_login(email: str) -> None:
        """Owner rule (2026-11-26): a client, employee or manager login must be an internal
        address (name@adverseindia.com); anything else is refused before anything is created."""
        domain = settings.internal_email_domain.strip().lower().lstrip("@")
        if domain and not settings.is_internal_email(email):
            raise RegistrationError(
                422,
                "LOGIN_NOT_INTERNAL",
                f"The login must be an internal address ending in @{domain}.",
            )

    def _require_actor(self, actor_id: UUID, required_role: RoleCode) -> ActorRecord:
        actor = self.repository.find_actor(actor_id)
        if actor is None:
            raise RegistrationError(404, "ACTOR_NOT_FOUND", "Creator does not exist.")
        if actor.status != UserStatus.ACTIVE:
            raise RegistrationError(403, "ACTOR_INACTIVE", "Creating user is not active.")
        if actor.role_code != required_role:
            raise RegistrationError(
                403, "CREATION_NOT_ALLOWED", "User cannot create this resource."
            )
        return actor

    def _start_verification(self, email: str) -> None:
        if self.verification_service is not None:
            self.verification_service.start_for_created_user(email)

    def _require_company_admin(self, actor_id: UUID, company_id: UUID) -> ActorRecord:
        actor = self._require_actor(actor_id, RoleCode.COMPANY_ADMIN)
        if actor.company_id != company_id:
            raise RegistrationError(
                403,
                "COMPANY_SCOPE_MISMATCH",
                "Company Admin cannot create users for another company.",
            )
        return actor

    def _require_active_company(self, company_id: UUID) -> CompanyRecord:
        company = self.repository.find_company(company_id)
        if company is None:
            raise RegistrationError(404, "COMPANY_NOT_FOUND", "Company does not exist.")
        if company.status != CompanyStatus.ACTIVE:
            raise RegistrationError(403, "COMPANY_INACTIVE", "Company is not active.")
        return company

    def _require_subscription_capacity(self, company: CompanyRecord) -> None:
        if not company.subscription_plan.strip():
            raise RegistrationError(
                403,
                "SUBSCRIPTION_REQUIRED",
                "Company subscription does not allow new users.",
            )

    def _enforce_limit(self, company_id: UUID, resource_code: str, actor_id: UUID) -> None:
        if self.enforcement_service is None:
            return
        try:
            self.enforcement_service.enforce_limit(
                company_id, resource_code, requested_increment=1, actor_id=actor_id
            )
        except AuthenticationError as error:
            raise RegistrationError(error.status_code, error.code, error.detail) from error


registration_service = RegistrationService()
