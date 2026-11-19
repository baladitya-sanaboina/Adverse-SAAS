import logging
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import JSONResponse

from app.api.agenda import router as agenda_router
from app.api.audit_logs import router as audit_logs_router
from app.api.authentication import router as authentication_router
from app.api.calendar import client_router as client_calendar_router
from app.api.calendar import router as calendar_router
from app.api.calendar import staff_router as staff_calendar_router
from app.api.chat import router as chat_router
from app.api.clients import router as clients_router
from app.api.company_dashboard import router as company_dashboard_router
from app.api.company_integrations import router as company_integrations_router
from app.api.company_management import router as company_management_router
from app.api.company_onboarding import router as company_onboarding_router
from app.api.company_settings import router as company_settings_router
from app.api.crm import router as crm_router
from app.api.developer_management import router as developer_management_router
from app.api.employees import router as employees_router
from app.api.finance import router as finance_router
from app.api.health import router as health_router
from app.api.invitations import router as invitations_router
from app.api.invoices import client_router as client_billing_router
from app.api.invoices import router as invoices_router
from app.api.mail import router as mail_router
from app.api.notifications import realtime_router
from app.api.notifications import router as notifications_router
from app.api.onboarding import public_router as public_onboarding_router
from app.api.onboarding import router as onboarding_router
from app.api.organization import router as organization_router
from app.api.platform_dashboard import router as platform_dashboard_router
from app.api.platform_settings import router as platform_settings_router
from app.api.profile import router as profile_router
from app.api.push import router as push_router
from app.api.registration import router as registration_router
from app.api.role_management import router as role_management_router
from app.api.service_pricing import router as service_pricing_router
from app.api.subscription_management import router as subscription_management_router
from app.api.tasks import router as tasks_router
from app.api.tenant import router as tenant_router
from app.api.user_assignments import router as user_assignments_router
from app.api.users import router as users_router
from app.api.workspace import portal_router as client_portal_router
from app.api.workspace import router as workspace_router
from app.core.settings import settings
from app.database.connectivity import close_database_pool, open_database_pool
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.middleware.tenant import TenantContextMiddleware
from app.services import default_admin_service, reminder_service
from app.services.authentication_service import AuthenticationError
from app.services.development_test_credentials_service import (
    development_test_credentials_service,
)
from app.services.registration_service import RegistrationError


class SensitiveQueryFilter(logging.Filter):
    """Prevent secret query parameters from reaching access-log output."""

    _token_pattern = re.compile(r"([?&]token=)[^&\s]+", re.IGNORECASE)

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple):
            record.args = tuple(
                self._token_pattern.sub(r"\1[REDACTED]", value) if isinstance(value, str) else value
                for value in record.args
            )
        return True


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    open_database_pool()
    development_test_credentials_service.ensure()
    default_admin_service.ensure()
    if settings.environment != "test":
        reminder_service.start()
    try:
        yield
    finally:
        reminder_service.stop()
        close_database_pool()


logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logging.getLogger("uvicorn.access").addFilter(SensitiveQueryFilter())

app = FastAPI(
    title=settings.app_name,
    summary=settings.app_description,
    description=(
        "Official API documentation for the Adverse local development backend. "
        f"Environment: {settings.environment}. Configuration, database, infrastructure, "
        "RBAC, tenant context, registration, and authentication foundations are exposed."
    ),
    version=settings.app_version,
    contact={
        "name": settings.swagger_contact_name,
        "email": settings.swagger_contact_email,
        "url": settings.swagger_contact_url,
    },
    docs_url="/docs" if settings.swagger_enabled else None,
    redoc_url="/redoc" if settings.swagger_enabled else None,
    openapi_url="/openapi.json" if settings.swagger_enabled else None,
    lifespan=lifespan,
    openapi_tags=[
        {
            "name": "health",
            "description": "Infrastructure connectivity and service readiness.",
        },
        {
            "name": "tenant",
            "description": "Active company context resolved by tenant middleware.",
        },
        {
            "name": "registration",
            "description": "Authorized company and user creation hierarchy.",
        },
        {
            "name": "authentication",
            "description": "Email verification, account activation, login, JWT access/refresh tokens, sessions, and protected routes.",
        },
        {
            "name": "users",
            "description": "Authenticated user profile, company, role, and permission context.",
        },
        {
            "name": "profile",
            "description": "Authenticated self-service profile, preferences, password, and image operations.",
        },
        {
            "name": "platform-dashboard",
            "description": "Platform Owner statistics, activity, quick actions, and system overview.",
        },
        {
            "name": "developer-management",
            "description": "Platform Owner Developer lifecycle, permissions, status, search, and pagination.",
        },
        {
            "name": "subscription-management",
            "description": "Platform plans, company assignments, feature enforcement, usage limits, warnings, and upgrade recommendations.",
        },
        {
            "name": "platform-settings",
            "description": "Global branding, SMTP, maintenance mode, and platform defaults.",
        },
        {
            "name": "company-onboarding",
            "description": "Transactional company, subscription, Company Admin, tenant defaults, and welcome setup.",
        },
        {
            "name": "company-settings",
            "description": "Tenant-isolated Company Admin profile, logo, visual branding, regional, contact, notification, and preference configuration.",
        },
        {
            "name": "company-integrations-workflows",
            "description": "Tenant-scoped integration configuration and basic workflow switches without provider credentials or adapters.",
        },
        {
            "name": "company-dashboard",
            "description": "Tenant-scoped Company Admin KPIs, recent activity, and permission-aware quick actions.",
        },
        {
            "name": "organization",
            "description": "Tenant-scoped Department and Branch structure management.",
        },
        {
            "name": "company-invitations",
            "description": "Secure tenant-bound company user invitation and account setup.",
        },
        {
            "name": "company-user-assignments",
            "description": "Transactional tenant-scoped role, department, and branch assignment.",
        },
        {
            "name": "company-role-management",
            "description": "Tenant-scoped custom role CRUD, permission selection, status, safe deletion, and audit logging.",
        },
        {
            "name": "employee-profiles",
            "description": "Tenant-scoped Employee business profiles linked to existing Users, Departments, Branches, and RBAC Roles.",
        },
        {
            "name": "client-management",
            "description": "Tenant-scoped client business records and one-to-many client contacts with existing Clients RBAC enforcement.",
        },
        {
            "name": "service-pricing",
            "description": "Tenant-scoped service catalog management plus client and manager pricing history.",
        },
        {
            "name": "crm-leads",
            "description": "Tenant-scoped CRM leads with optional Client association and same-company Employee ownership.",
        },
        {
            "name": "crm-opportunities",
            "description": "Tenant-scoped qualified opportunities linked to Clients, originating Leads, and Employee owners.",
        },
        {
            "name": "crm-pipeline",
            "description": "Tenant-scoped CRM pipeline relationship choices used by authorized company workspaces.",
        },
        {
            "name": "audit-logs",
            "description": "Platform Owner read-only inventory of critical platform management audit events.",
        },
        {
            "name": "tasks",
            "description": "Company Admin task management: create with price snapshot, assign, re-price, approve, files and comments.",
        },
        {
            "name": "team-workspace",
            "description": "Manager and Employee workspace: own tasks, status updates, deliverables and own earnings only.",
        },
        {
            "name": "client-portal",
            "description": "Client's own work counts, budget and payments. No task list and no internal costs.",
        },
        {
            "name": "finance",
            "description": "Company Admin money: revenue, margin, budgets, client payments, salaries, payouts and reports.",
        },
    ],
)


@app.exception_handler(RegistrationError)
async def registration_error_handler(_: Request, error: RegistrationError) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code,
        content={"code": error.code, "detail": error.detail, "errors": None},
    )


@app.exception_handler(AuthenticationError)
async def authentication_error_handler(_: Request, error: AuthenticationError) -> JSONResponse:
    headers = {"WWW-Authenticate": "Bearer"} if error.status_code == 401 else None
    return JSONResponse(
        status_code=error.status_code,
        content={"code": error.code, "detail": error.detail, "errors": None},
        headers=headers,
    )


@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(
    _: Request, error: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "code": "VALIDATION_ERROR",
            "detail": "Request validation failed.",
            "errors": jsonable_encoder(error.errors()),
        },
    )


if settings.health_check_enabled:
    app.include_router(health_router, prefix=settings.api_prefix)
app.include_router(tenant_router, prefix=settings.api_prefix)
app.include_router(registration_router, prefix=settings.api_prefix)
app.include_router(authentication_router, prefix=settings.api_prefix)
app.include_router(users_router, prefix=settings.api_prefix)
app.include_router(profile_router, prefix=settings.api_prefix)
app.include_router(platform_dashboard_router, prefix=settings.api_prefix)
app.include_router(developer_management_router, prefix=settings.api_prefix)
app.include_router(company_management_router, prefix=settings.api_prefix)
app.include_router(subscription_management_router, prefix=settings.api_prefix)
app.include_router(platform_settings_router, prefix=settings.api_prefix)
app.include_router(company_onboarding_router, prefix=settings.api_prefix)
app.include_router(company_settings_router, prefix=settings.api_prefix)
app.include_router(company_integrations_router, prefix=settings.api_prefix)
app.include_router(company_dashboard_router, prefix=settings.api_prefix)
app.include_router(organization_router, prefix=settings.api_prefix)
app.include_router(invitations_router, prefix=settings.api_prefix)
app.include_router(user_assignments_router, prefix=settings.api_prefix)
app.include_router(role_management_router, prefix=settings.api_prefix)
app.include_router(employees_router, prefix=settings.api_prefix)
app.include_router(clients_router, prefix=settings.api_prefix)
app.include_router(service_pricing_router, prefix=settings.api_prefix)
app.include_router(tasks_router, prefix=settings.api_prefix)
app.include_router(workspace_router, prefix=settings.api_prefix)
app.include_router(client_portal_router, prefix=settings.api_prefix)
app.include_router(notifications_router, prefix=settings.api_prefix)
app.include_router(realtime_router, prefix=settings.api_prefix)
app.include_router(invoices_router, prefix=settings.api_prefix)
app.include_router(client_billing_router, prefix=settings.api_prefix)
app.include_router(finance_router, prefix=settings.api_prefix)
app.include_router(calendar_router, prefix=settings.api_prefix)
app.include_router(client_calendar_router, prefix=settings.api_prefix)
app.include_router(staff_calendar_router, prefix=settings.api_prefix)
app.include_router(chat_router, prefix=settings.api_prefix)
app.include_router(mail_router, prefix=settings.api_prefix)
app.include_router(agenda_router, prefix=settings.api_prefix)
app.include_router(push_router, prefix=settings.api_prefix)
app.include_router(onboarding_router, prefix=settings.api_prefix)
app.include_router(public_onboarding_router, prefix=settings.api_prefix)
app.include_router(crm_router, prefix=settings.api_prefix)
app.include_router(audit_logs_router, prefix=settings.api_prefix)
# Public logos and profile pictures. The folder only appears after the first upload, and a
# missing folder made every /storage request a 500, so create it up front.
PUBLIC_STORAGE = Path("storage")
PUBLIC_STORAGE.mkdir(parents=True, exist_ok=True)
app.mount("/storage", StaticFiles(directory=PUBLIC_STORAGE), name="storage")
app.add_middleware(
    TenantContextMiddleware,
    exempt_path_prefixes={
        "/storage/profile-images/",
        "/storage/company-branding/",
        f"{settings.api_prefix}/public/onboarding/",
        f"{settings.api_prefix}/platform/developers",
        f"{settings.api_prefix}/platform/companies",
        f"{settings.api_prefix}/platform/subscription-plans",
        f"{settings.api_prefix}/platform/settings",
        f"{settings.api_prefix}/platform/onboarding",
        f"{settings.api_prefix}/platform/audit-logs",
        f"{settings.api_prefix}/company/settings",
        f"{settings.api_prefix}/company/branding",
        f"{settings.api_prefix}/company/integrations",
        f"{settings.api_prefix}/company/workflow-settings",
        f"{settings.api_prefix}/company/dashboard",
        f"{settings.api_prefix}/company/departments",
        f"{settings.api_prefix}/company/branches",
        f"{settings.api_prefix}/company/invitations",
        f"{settings.api_prefix}/company/users",
        f"{settings.api_prefix}/company/roles",
        f"{settings.api_prefix}/company/employees",
        f"{settings.api_prefix}/clients",
        f"{settings.api_prefix}/leads",
        f"{settings.api_prefix}/opportunities",
        f"{settings.api_prefix}/crm",
    },
    exempt_paths={
        f"{settings.api_prefix}/health",
        "/docs",
        "/redoc",
        "/openapi.json",
        f"{settings.api_prefix}/registration/developers",
        f"{settings.api_prefix}/registration/companies",
        f"{settings.api_prefix}/registration/company-admins",
        f"{settings.api_prefix}/registration/employees",
        f"{settings.api_prefix}/registration/clients",
        f"{settings.api_prefix}/auth/login",
        f"{settings.api_prefix}/auth/signup",
        f"{settings.api_prefix}/auth/forgot-password",
        f"{settings.api_prefix}/auth/reset-password",
        f"{settings.api_prefix}/auth/send-verification-email",
        f"{settings.api_prefix}/auth/resend-verification",
        f"{settings.api_prefix}/auth/verify-email",
        f"{settings.api_prefix}/auth/refresh",
        f"{settings.api_prefix}/auth/me",
        f"{settings.api_prefix}/auth/logout",
        f"{settings.api_prefix}/users/me",
        f"{settings.api_prefix}/profile",
        f"{settings.api_prefix}/profile/change-password",
        f"{settings.api_prefix}/profile/image",
        f"{settings.api_prefix}/platform/dashboard",
    },
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware)
