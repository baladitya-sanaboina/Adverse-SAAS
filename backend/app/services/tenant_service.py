from uuid import UUID

from app.core.constants import (
    ERROR_COMPANY_NOT_FOUND,
    ERROR_INVALID_TENANT,
    CompanyStatus,
)
from app.repositories.tenant_repository import CompanyRecord, TenantRepository


class InvalidTenantIdentifier(ValueError):
    pass


class TenantNotFound(LookupError):
    pass


class TenantUnavailable(PermissionError):
    def __init__(self, status: str):
        self.status = status
        super().__init__(f"Company is {status.lower()}.")


class TenantService:
    def __init__(self, repository: TenantRepository | None = None):
        self.repository = repository or TenantRepository()

    def get_current_company(self, company_id: str) -> CompanyRecord:
        try:
            normalized_id = str(UUID(company_id))
        except (ValueError, TypeError) as error:
            raise InvalidTenantIdentifier(ERROR_INVALID_TENANT) from error

        company = self.repository.find_company(normalized_id)
        if company is None:
            raise TenantNotFound(ERROR_COMPANY_NOT_FOUND)
        return company

    def validate_company_status(self, company: CompanyRecord) -> None:
        if company.status != CompanyStatus.ACTIVE:
            raise TenantUnavailable(company.status)

    def resolve_tenant(self, company_id: str) -> CompanyRecord:
        company = self.get_current_company(company_id)
        self.validate_company_status(company)
        return company

    def is_ready(self) -> bool:
        return self.repository.foundation_is_ready()


tenant_service = TenantService()
