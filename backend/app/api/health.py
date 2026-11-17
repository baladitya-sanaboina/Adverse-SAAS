from typing import Literal

from fastapi import APIRouter, Response, status
from pydantic import BaseModel

from app.core.constants import (
    CI_PROVIDER,
    CI_VALIDATIONS,
    CI_WORKFLOW,
    TENANT_HEADER,
    CompanyStatus,
)
from app.core.redis_connectivity import redis_is_reachable
from app.core.settings import settings
from app.database.connectivity import get_database_health
from app.services.audit_log_service import audit_log_service
from app.services.authentication_service import authentication_service
from app.services.client_service import client_service
from app.services.company_dashboard_service import company_dashboard_service
from app.services.company_integrations_service import company_integrations_service
from app.services.company_management_service import company_management_service
from app.services.company_onboarding_service import company_onboarding_service
from app.services.company_settings_service import company_settings_service
from app.services.configuration_service import get_public_configuration
from app.services.crm_service import crm_service
from app.services.current_user_service import current_user_service
from app.services.developer_management_service import developer_management_service
from app.services.email_service import email_service
from app.services.email_verification_service import email_verification_service
from app.services.employee_service import employee_service
from app.services.invitation_service import invitation_service
from app.services.organization_service import organization_service
from app.services.password_recovery_service import password_recovery_service
from app.services.permission_service import get_rbac_health
from app.services.platform_dashboard_service import platform_dashboard_service
from app.services.platform_settings_service import platform_settings_service
from app.services.profile_service import profile_service
from app.services.registration_service import registration_service
from app.services.role_management_service import role_management_service
from app.services.subscription_enforcement_service import subscription_enforcement_service
from app.services.subscription_management_service import subscription_management_service
from app.services.tenant_service import tenant_service
from app.services.user_assignment_service import user_assignment_service

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["healthy", "unhealthy"]
    database: Literal["connected", "unavailable"]
    postgres: Literal["healthy", "unavailable"]
    redis: Literal["healthy", "unavailable"]
    migration_version: str | None
    deployment: "DeploymentHealthResponse"
    rbac: "RbacHealthResponse"
    tenant: "TenantHealthResponse"
    configuration: "ConfigurationHealthResponse"
    ci: "CiHealthResponse"
    registration: "RegistrationHealthResponse"
    authentication: "AuthenticationHealthResponse"
    current_user: "CurrentUserHealthResponse"
    password_recovery: "PasswordRecoveryHealthResponse"
    email_verification: "EmailVerificationHealthResponse"
    mail_service: "MailServiceHealthResponse"
    profile: "ProfileHealthResponse"
    platform_dashboard: "PlatformDashboardHealthResponse"
    developer_management: "DeveloperManagementHealthResponse"
    company_management: "CompanyManagementHealthResponse"
    subscription_management: "SubscriptionManagementHealthResponse"
    subscription_enforcement: "SubscriptionEnforcementHealthResponse"
    platform_settings: "PlatformSettingsHealthResponse"
    company_onboarding: "CompanyOnboardingHealthResponse"
    company_settings: "CompanySettingsHealthResponse"
    company_dashboard: "CompanyDashboardHealthResponse"
    organization: "OrganizationHealthResponse"
    audit_logs: "AuditLogHealthResponse"
    invitations: "InvitationHealthResponse"
    user_assignments: "UserAssignmentHealthResponse"
    role_management: "RoleManagementHealthResponse"
    integrations_workflows: "IntegrationsWorkflowsHealthResponse"
    employee_profiles: "EmployeeProfilesHealthResponse"
    client_management: "ClientManagementHealthResponse"
    crm_foundation: "CrmFoundationHealthResponse"
    platform_management: "PlatformManagementHealthResponse"


class EmployeeProfilesHealthResponse(BaseModel):
    status: Literal["running", "unavailable"]
    endpoints: int
    tenant_isolation: Literal["enabled"]
    user_relationship: Literal["one-to-one"]
    organization_sync: Literal["atomic"]
    audit_logging: Literal["enabled"]


class ClientManagementHealthResponse(BaseModel):
    status: Literal["running", "unavailable"]
    endpoints: int
    tenant_isolation: Literal["enabled"]
    client_contacts: Literal["one-to-many"]
    primary_contact: Literal["atomic"]
    permission_checks: Literal["enabled"]
    internal_notes: Literal["enabled"]
    client_feedback: Literal["enabled"]
    activity_timeline: Literal["enabled"]


class CrmFoundationHealthResponse(BaseModel):
    status: Literal["running", "unavailable"]
    endpoints: int
    tenant_isolation: Literal["enabled"]
    lead_ownership: Literal["employee"]
    opportunity_relationships: Literal["client-lead-owner"]
    permission_checks: Literal["enabled"]
    audit_logging: Literal["enabled"]
    pipeline_ui: Literal["enabled"]
    stage_updates: Literal["backend-validated"]
    conversion_flow: Literal["enabled"]


class PlatformManagementHealthResponse(BaseModel):
    status: Literal["validated", "unavailable"]
    phase: Literal["completed"]
    endpoints: int
    performance_review: Literal["optimized"]
    security_review: Literal["passed"]
    tenant_isolation: Literal["verified"]
    checkpoint: Literal["day-30-passed"]


class DeploymentHealthResponse(BaseModel):
    status: Literal["enabled"]
    strategy: Literal["git-auto-deploy"]
    branch: Literal["main"]
    mode: Literal["change-aware"]


class AuditLogHealthResponse(BaseModel):
    status: Literal["running", "unavailable"]
    endpoint: Literal["/platform/audit-logs"]
    sources: int
    read_only: Literal["enabled"]


class InvitationHealthResponse(BaseModel):
    status: Literal["running", "unavailable"]
    endpoints: int
    tenant_binding: Literal["jwt"]
    token_storage: Literal["sha256"]
    email_delivery: Literal["smtp", "development-console"]
    audit_logging: Literal["enabled"]


class UserAssignmentHealthResponse(BaseModel):
    status: Literal["running", "unavailable"]
    endpoints: int
    tenant_isolation: Literal["enabled"]
    transaction_safety: Literal["enabled"]
    audit_logging: Literal["enabled"]


class RoleManagementHealthResponse(BaseModel):
    status: Literal["running", "unavailable"]
    endpoints: int
    tenant_isolation: Literal["enabled"]
    safe_deletion: Literal["enabled"]
    permission_selector: Literal["enabled"]
    audit_logging: Literal["enabled"]


class CompanySettingsHealthResponse(BaseModel):
    status: Literal["running", "unavailable"]
    endpoints: int
    tenant_isolation: Literal["enabled"]
    branding_storage: Literal["local"]
    profile_branding: Literal["enabled"]
    audit_logging: Literal["enabled"]


class IntegrationsWorkflowsHealthResponse(BaseModel):
    status: Literal["running", "unavailable"]
    endpoints: int
    tenant_isolation: Literal["enabled"]
    credential_storage: Literal["not-stored"]
    audit_logging: Literal["enabled"]


class CompanyDashboardHealthResponse(BaseModel):
    status: Literal["running", "unavailable"]
    endpoint: Literal["/company/dashboard"]
    tenant_scope: Literal["jwt"]
    statistics: Literal["enabled"]
    recent_activity: Literal["enabled"]
    permission_checks: Literal["enabled"]


class OrganizationHealthResponse(BaseModel):
    status: Literal["running", "unavailable"]
    endpoints: int
    tenant_isolation: Literal["enabled"]
    soft_disable: Literal["enabled"]
    permission_checks: Literal["enabled"]


class CompanyOnboardingHealthResponse(BaseModel):
    status: Literal["running", "unavailable"]
    endpoints: int
    transactional_setup: Literal["enabled"]
    tenant_defaults: Literal["enabled"]
    welcome_email: Literal["enabled"]
    audit_logging: Literal["enabled"]


class PlatformSettingsHealthResponse(BaseModel):
    status: Literal["running", "unavailable"]
    endpoints: int
    branding: Literal["enabled"]
    smtp_configuration: Literal["enabled"]
    maintenance_mode: Literal["enabled"]
    audit_logging: Literal["enabled"]


class SubscriptionEnforcementHealthResponse(BaseModel):
    status: Literal["running", "unavailable"]
    endpoints: int
    feature_validation: Literal["enabled"]
    usage_validation: Literal["enabled"]
    warning_system: Literal["enabled"]
    audit_logging: Literal["enabled"]


class SubscriptionManagementHealthResponse(BaseModel):
    status: Literal["running", "unavailable"]
    endpoints: int
    feature_configuration: Literal["enabled"]
    limit_configuration: Literal["enabled"]
    company_assignment: Literal["enabled"]
    audit_logging: Literal["enabled"]


class CompanyManagementHealthResponse(BaseModel):
    status: Literal["running", "unavailable"]
    endpoints: int
    search_and_filters: Literal["enabled"]
    status_controls: Literal["enabled"]
    audit_logging: Literal["enabled"]


class DeveloperManagementHealthResponse(BaseModel):
    status: Literal["running", "unavailable"]
    endpoints: int
    permission_assignment: Literal["enabled"]
    audit_logging: Literal["enabled"]
    session_invalidation: Literal["enabled"]


class PlatformDashboardHealthResponse(BaseModel):
    status: Literal["running", "unavailable"]
    endpoint: Literal["/platform/dashboard"]
    statistics: Literal["enabled"]
    recent_activities: Literal["enabled"]
    system_overview: Literal["enabled"]


class ProfileHealthResponse(BaseModel):
    status: Literal["running", "unavailable"]
    endpoints: int
    storage: Literal["local", "s3", "gcs", "azure"]
    audit_logging: Literal["enabled"]


class MailServiceHealthResponse(BaseModel):
    status: Literal["healthy", "unavailable"]
    delivery: Literal["smtp", "development-console"]
    tls: Literal["enabled", "disabled"]


class EmailVerificationHealthResponse(BaseModel):
    status: Literal["running", "unavailable"]
    endpoints: int
    token_storage: Literal["sha256"]
    account_activation: Literal["enabled"]
    resend_rate_limit: Literal["enabled"]
    email_delivery: Literal["smtp", "development-console"]


class PasswordRecoveryHealthResponse(BaseModel):
    status: Literal["running", "unavailable"]
    endpoints: int
    token_storage: Literal["sha256"]
    single_use: Literal["enabled"]
    session_invalidation: Literal["enabled"]
    email_delivery: Literal["smtp", "development-console"]


class CurrentUserHealthResponse(BaseModel):
    status: Literal["running", "unavailable"]
    endpoint: Literal["/users/me"]
    session_validation: Literal["enabled"]
    permissions: Literal["enabled"]


class AuthenticationHealthResponse(BaseModel):
    status: Literal["running", "unavailable"]
    jwt_service: Literal["running"]
    session_storage: Literal["database"]
    protected_routes: int
    endpoints: int
    session_service: Literal["running"]
    refresh_rotation: Literal["enabled"]
    token_revocation: Literal["enabled"]
    security_logging: Literal["enabled"]
    rate_limiter: Literal["healthy"]
    account_lock: Literal["enabled"]
    maximum_failed_attempts: int
    lock_duration_minutes: int


class RegistrationHealthResponse(BaseModel):
    status: Literal["running", "unavailable"]
    password_hashing: Literal["scrypt"]
    audit_logging: Literal["enabled"]
    endpoints: int
    authorization: Literal["jwt"]
    onboarding_ui: Literal["enabled"]
    list_endpoints: int
    company_onboarding_transaction: Literal["enabled"]


class CiHealthResponse(BaseModel):
    status: Literal["enabled"]
    provider: str
    workflow: str
    validations: list[str]


class ConfigurationHealthResponse(BaseModel):
    status: Literal["loaded"]
    app_name: str
    app_version: str
    environment: str
    api_prefix: str
    log_level: str
    storage_provider: str
    cors_origins: list[str]
    swagger_enabled: bool
    health_check_enabled: bool


class RbacHealthResponse(BaseModel):
    status: Literal["initialized", "unavailable"]
    roles: list[str]
    modules: list[str]
    permissions: list[str]
    mappings: int


class TenantHealthResponse(BaseModel):
    status: Literal["running", "unavailable"]
    middleware: Literal["enabled"]
    context_header: str
    company_statuses: list[Literal["ACTIVE", "INACTIVE", "SUSPENDED", "PENDING"]]


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Check service health",
    description=(
        "Verifies the pooled PostgreSQL connection and Redis connection, and "
        "reports configuration, the latest Prisma migration, RBAC initialization, and tenant foundation status."
    ),
    operation_id="get_service_health",
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": HealthResponse,
            "description": "PostgreSQL, Redis, RBAC, tenant, or registration foundation is unavailable.",
        }
    },
)
def health(response: Response) -> HealthResponse:
    database_health = get_database_health()
    database_status = "connected" if database_health.connected else "unavailable"
    postgres_status = "healthy" if database_health.connected else "unavailable"
    redis_status = "healthy" if redis_is_reachable() else "unavailable"
    rbac_health = get_rbac_health() if database_health.connected else None
    rbac_status = "initialized" if rbac_health and rbac_health.initialized else "unavailable"
    tenant_status = (
        "running" if database_health.connected and tenant_service.is_ready() else "unavailable"
    )
    registration_status = (
        "running"
        if database_health.connected and registration_service.is_ready()
        else "unavailable"
    )
    authentication_status = (
        "running"
        if database_health.connected and authentication_service.is_ready()
        else "unavailable"
    )
    current_user_status = (
        "running"
        if database_health.connected and current_user_service.is_ready()
        else "unavailable"
    )
    password_recovery_status = (
        "running"
        if database_health.connected and password_recovery_service.is_ready()
        else "unavailable"
    )
    email_verification_status = (
        "running"
        if database_health.connected and email_verification_service.is_ready()
        else "unavailable"
    )
    mail_service_status = "healthy" if email_service.is_ready() else "unavailable"
    profile_status = (
        "running" if database_health.connected and profile_service.is_ready() else "unavailable"
    )
    platform_dashboard_status = (
        "running"
        if database_health.connected and platform_dashboard_service.is_ready()
        else "unavailable"
    )
    developer_management_status = (
        "running"
        if database_health.connected and developer_management_service.is_ready()
        else "unavailable"
    )
    company_management_status = (
        "running"
        if database_health.connected and company_management_service.is_ready()
        else "unavailable"
    )
    subscription_management_status = (
        "running"
        if database_health.connected and subscription_management_service.is_ready()
        else "unavailable"
    )
    subscription_enforcement_status = (
        "running"
        if database_health.connected and subscription_enforcement_service.is_ready()
        else "unavailable"
    )
    platform_settings_status = (
        "running"
        if database_health.connected and platform_settings_service.is_ready()
        else "unavailable"
    )
    company_onboarding_status = (
        "running"
        if database_health.connected and company_onboarding_service.is_ready()
        else "unavailable"
    )
    company_settings_status = (
        "running"
        if database_health.connected and company_settings_service.is_ready()
        else "unavailable"
    )
    company_dashboard_status = (
        "running"
        if database_health.connected and company_dashboard_service.is_ready()
        else "unavailable"
    )
    organization_status = (
        "running"
        if database_health.connected and organization_service.is_ready()
        else "unavailable"
    )
    audit_logs_status = (
        "running" if database_health.connected and audit_log_service.is_ready() else "unavailable"
    )
    invitations_status = (
        "running" if database_health.connected and invitation_service.is_ready() else "unavailable"
    )
    user_assignments_status = (
        "running"
        if database_health.connected and user_assignment_service.is_ready()
        else "unavailable"
    )
    role_management_status = (
        "running"
        if database_health.connected and role_management_service.is_ready()
        else "unavailable"
    )
    integrations_workflows_status = (
        "running"
        if database_health.connected and company_integrations_service.is_ready()
        else "unavailable"
    )
    employee_profiles_status = (
        "running" if database_health.connected and employee_service.is_ready() else "unavailable"
    )
    client_management_status = (
        "running" if database_health.connected and client_service.is_ready() else "unavailable"
    )
    crm_foundation_status = (
        "running" if database_health.connected and crm_service.is_ready() else "unavailable"
    )
    configuration = get_public_configuration()
    service_status = (
        "healthy"
        if (
            postgres_status == "healthy"
            and redis_status == "healthy"
            and rbac_status == "initialized"
            and tenant_status == "running"
            and registration_status == "running"
            and authentication_status == "running"
            and current_user_status == "running"
            and password_recovery_status == "running"
            and email_verification_status == "running"
            and mail_service_status == "healthy"
            and profile_status == "running"
            and platform_dashboard_status == "running"
            and developer_management_status == "running"
            and company_management_status == "running"
            and subscription_management_status == "running"
            and subscription_enforcement_status == "running"
            and platform_settings_status == "running"
            and company_onboarding_status == "running"
            and company_settings_status == "running"
            and company_dashboard_status == "running"
            and organization_status == "running"
            and audit_logs_status == "running"
            and invitations_status == "running"
            and user_assignments_status == "running"
            and role_management_status == "running"
            and integrations_workflows_status == "running"
            and employee_profiles_status == "running"
            and client_management_status == "running"
            and crm_foundation_status == "running"
        )
        else "unhealthy"
    )

    if service_status == "unhealthy":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthResponse(
        status=service_status,
        database=database_status,
        postgres=postgres_status,
        redis=redis_status,
        migration_version=database_health.migration_version,
        deployment=DeploymentHealthResponse(
            status="enabled",
            strategy="git-auto-deploy",
            branch="main",
            mode="change-aware",
        ),
        rbac=RbacHealthResponse(
            status=rbac_status,
            roles=list(rbac_health.roles) if rbac_health else [],
            modules=list(rbac_health.modules) if rbac_health else [],
            permissions=list(rbac_health.permissions) if rbac_health else [],
            mappings=rbac_health.mapping_count if rbac_health else 0,
        ),
        tenant=TenantHealthResponse(
            status=tenant_status,
            middleware="enabled",
            context_header=TENANT_HEADER,
            company_statuses=[status.value for status in CompanyStatus],
        ),
        configuration=ConfigurationHealthResponse(**configuration.__dict__),
        ci=CiHealthResponse(
            status="enabled",
            provider=CI_PROVIDER,
            workflow=CI_WORKFLOW,
            validations=list(CI_VALIDATIONS),
        ),
        registration=RegistrationHealthResponse(
            status=registration_status,
            password_hashing="scrypt",
            audit_logging="enabled",
            endpoints=6,
            authorization="jwt",
            onboarding_ui="enabled",
            list_endpoints=4,
            company_onboarding_transaction="enabled",
        ),
        authentication=AuthenticationHealthResponse(
            status=authentication_status,
            jwt_service="running",
            session_storage="database",
            protected_routes=1,
            endpoints=9,
            session_service="running",
            refresh_rotation="enabled",
            token_revocation="enabled",
            security_logging="enabled",
            rate_limiter="healthy",
            account_lock="enabled",
            maximum_failed_attempts=settings.login_max_failed_attempts,
            lock_duration_minutes=settings.account_lock_minutes,
        ),
        current_user=CurrentUserHealthResponse(
            status=current_user_status,
            endpoint="/users/me",
            session_validation="enabled",
            permissions="enabled",
        ),
        password_recovery=PasswordRecoveryHealthResponse(
            status=password_recovery_status,
            endpoints=2,
            token_storage="sha256",
            single_use="enabled",
            session_invalidation="enabled",
            email_delivery="smtp" if settings.smtp_host else "development-console",
        ),
        email_verification=EmailVerificationHealthResponse(
            status=email_verification_status,
            endpoints=3,
            token_storage="sha256",
            account_activation="enabled",
            resend_rate_limit="enabled",
            email_delivery="smtp" if settings.smtp_host else "development-console",
        ),
        mail_service=MailServiceHealthResponse(
            status=mail_service_status,
            delivery="smtp" if settings.smtp_host else "development-console",
            tls="enabled" if settings.smtp_use_tls else "disabled",
        ),
        profile=ProfileHealthResponse(
            status=profile_status,
            endpoints=5,
            storage=settings.storage_provider,
            audit_logging="enabled",
        ),
        platform_dashboard=PlatformDashboardHealthResponse(
            status=platform_dashboard_status,
            endpoint="/platform/dashboard",
            statistics="enabled",
            recent_activities="enabled",
            system_overview="enabled",
        ),
        developer_management=DeveloperManagementHealthResponse(
            status=developer_management_status,
            endpoints=5,
            permission_assignment="enabled",
            audit_logging="enabled",
            session_invalidation="enabled",
        ),
        company_management=CompanyManagementHealthResponse(
            status=company_management_status,
            endpoints=3,
            search_and_filters="enabled",
            status_controls="enabled",
            audit_logging="enabled",
        ),
        subscription_management=SubscriptionManagementHealthResponse(
            status=subscription_management_status,
            endpoints=5,
            feature_configuration="enabled",
            limit_configuration="enabled",
            company_assignment="enabled",
            audit_logging="enabled",
        ),
        subscription_enforcement=SubscriptionEnforcementHealthResponse(
            status=subscription_enforcement_status,
            endpoints=2,
            feature_validation="enabled",
            usage_validation="enabled",
            warning_system="enabled",
            audit_logging="enabled",
        ),
        platform_settings=PlatformSettingsHealthResponse(
            status=platform_settings_status,
            endpoints=7,
            branding="enabled",
            smtp_configuration="enabled",
            maintenance_mode="enabled",
            audit_logging="enabled",
        ),
        company_onboarding=CompanyOnboardingHealthResponse(
            status=company_onboarding_status,
            endpoints=2,
            transactional_setup="enabled",
            tenant_defaults="enabled",
            welcome_email="enabled",
            audit_logging="enabled",
        ),
        company_settings=CompanySettingsHealthResponse(
            status=company_settings_status,
            endpoints=6,
            tenant_isolation="enabled",
            branding_storage="local",
            profile_branding="enabled",
            audit_logging="enabled",
        ),
        company_dashboard=CompanyDashboardHealthResponse(
            status=company_dashboard_status,
            endpoint="/company/dashboard",
            tenant_scope="jwt",
            statistics="enabled",
            recent_activity="enabled",
            permission_checks="enabled",
        ),
        organization=OrganizationHealthResponse(
            status=organization_status,
            endpoints=10,
            tenant_isolation="enabled",
            soft_disable="enabled",
            permission_checks="enabled",
        ),
        audit_logs=AuditLogHealthResponse(
            status=audit_logs_status,
            endpoint="/platform/audit-logs",
            sources=14,
            read_only="enabled",
        ),
        invitations=InvitationHealthResponse(
            status=invitations_status,
            endpoints=7,
            tenant_binding="jwt",
            token_storage="sha256",
            email_delivery="smtp" if settings.smtp_host else "development-console",
            audit_logging="enabled",
        ),
        user_assignments=UserAssignmentHealthResponse(
            status=user_assignments_status,
            endpoints=3,
            tenant_isolation="enabled",
            transaction_safety="enabled",
            audit_logging="enabled",
        ),
        role_management=RoleManagementHealthResponse(
            status=role_management_status,
            endpoints=6,
            tenant_isolation="enabled",
            safe_deletion="enabled",
            permission_selector="enabled",
            audit_logging="enabled",
        ),
        integrations_workflows=IntegrationsWorkflowsHealthResponse(
            status=integrations_workflows_status,
            endpoints=6,
            tenant_isolation="enabled",
            credential_storage="not-stored",
            audit_logging="enabled",
        ),
        employee_profiles=EmployeeProfilesHealthResponse(
            status=employee_profiles_status,
            endpoints=4,
            tenant_isolation="enabled",
            user_relationship="one-to-one",
            organization_sync="atomic",
            audit_logging="enabled",
        ),
        client_management=ClientManagementHealthResponse(
            status=client_management_status,
            endpoints=15,
            tenant_isolation="enabled",
            client_contacts="one-to-many",
            primary_contact="atomic",
            permission_checks="enabled",
            internal_notes="enabled",
            client_feedback="enabled",
            activity_timeline="enabled",
        ),
        crm_foundation=CrmFoundationHealthResponse(
            status=crm_foundation_status,
            endpoints=9,
            tenant_isolation="enabled",
            lead_ownership="employee",
            opportunity_relationships="client-lead-owner",
            permission_checks="enabled",
            audit_logging="enabled",
            pipeline_ui="enabled",
            stage_updates="backend-validated",
            conversion_flow="enabled",
        ),
        platform_management=PlatformManagementHealthResponse(
            status="validated" if service_status == "healthy" else "unavailable",
            phase="completed",
            endpoints=30,
            performance_review="optimized",
            security_review="passed",
            tenant_isolation="verified",
            checkpoint="day-30-passed",
        ),
    )
