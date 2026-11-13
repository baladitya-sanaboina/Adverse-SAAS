from enum import StrEnum


class RoleCode(StrEnum):
    PLATFORM_OWNER = "PLATFORM_OWNER"
    DEVELOPER = "DEVELOPER"
    COMPANY_ADMIN = "COMPANY_ADMIN"
    COMPANY_MANAGER = "COMPANY_MANAGER"
    COMPANY_EMPLOYEE = "COMPANY_EMPLOYEE"
    COMPANY_CLIENT = "COMPANY_CLIENT"


class CompanyStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    SUSPENDED = "SUSPENDED"
    PENDING = "PENDING"


class UserStatus(StrEnum):
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    SUSPENDED = "SUSPENDED"


class SubscriptionStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

TENANT_HEADER = "X-Company-ID"
MESSAGE_CONFIGURATION_LOADED = "Application configuration loaded."
CI_PROVIDER = "GitHub Actions"
CI_WORKFLOW = ".github/workflows/ci.yml"
CI_VALIDATIONS = ("dependencies", "format", "lint", "type-check", "tests", "build", "startup")
ERROR_TENANT_REQUIRED = f"{TENANT_HEADER} header is required."
ERROR_INVALID_TENANT = f"{TENANT_HEADER} must be a valid UUID."
ERROR_COMPANY_NOT_FOUND = "Company not found."
