from dataclasses import dataclass
from uuid import UUID

from app.repositories.subscription_enforcement_repository import (
    EnforcementSnapshot,
    SubscriptionEnforcementRepository,
)
from app.schemas.authentication import AuthContext
from app.schemas.subscription_enforcement import (
    CompanyUsageResponse,
    SubscriptionEnforcementResponse,
    SubscriptionValidationRequest,
    UsageAlertResponse,
    UsageMetricResponse,
)
from app.services.authentication_service import AuthenticationError
from app.services.permission_service import validate_user_action_access

GIB = 1024**3


@dataclass(frozen=True)
class ResourceValue:
    code: str
    label: str
    used_raw: int
    limit_raw: int | None
    unit: str
    divisor: int = 1


class SubscriptionEnforcementService:
    def __init__(self, repository: SubscriptionEnforcementRepository | None = None):
        self.repository = repository or SubscriptionEnforcementRepository()

    @staticmethod
    def _authorize(context: AuthContext) -> None:
        if not validate_user_action_access(str(context.user_id), context.role, "COMPANIES", "VIEW"):
            raise AuthenticationError(
                403, "PERMISSION_DENIED", "VIEW access to COMPANIES is required."
            )

    def _snapshot(self, company_id: UUID) -> EnforcementSnapshot:
        snapshot = self.repository.snapshot(company_id)
        if snapshot:
            return snapshot
        if not self.repository.company_exists(company_id):
            raise AuthenticationError(404, "COMPANY_NOT_FOUND", "Company does not exist.")
        raise AuthenticationError(
            403,
            "SUBSCRIPTION_REQUIRED",
            "Company does not have an active subscription plan.",
        )

    @staticmethod
    def _resources(snapshot: EnforcementSnapshot) -> tuple[ResourceValue, ...]:
        limits = snapshot.limits
        storage_limit = limits.get("MAX_STORAGE_GB")
        return (
            ResourceValue(
                "MAX_EMPLOYEES",
                "Employees",
                snapshot.employees_used,
                limits.get("MAX_EMPLOYEES"),
                "users",
            ),
            ResourceValue(
                "MAX_CLIENTS",
                "Clients",
                snapshot.clients_used,
                limits.get("MAX_CLIENTS"),
                "clients",
            ),
            ResourceValue(
                "MAX_PROJECTS",
                "Projects",
                snapshot.projects_used,
                limits.get("MAX_PROJECTS"),
                "projects",
            ),
            ResourceValue(
                "MAX_STORAGE_GB",
                "Storage",
                snapshot.storage_used_bytes,
                storage_limit * GIB if storage_limit is not None else None,
                "GB",
                GIB,
            ),
        )

    @staticmethod
    def _state(used: int, limit: int | None) -> str:
        if limit is None:
            return "UNLIMITED"
        if limit == 0 or used >= limit:
            return "LIMIT_REACHED"
        percentage = used / limit * 100
        if percentage >= 90:
            return "HIGH_USAGE"
        if percentage >= 80:
            return "WARNING"
        return "OK"

    def _metric(
        self, snapshot: EnforcementSnapshot, resource: ResourceValue
    ) -> UsageMetricResponse:
        state = self._state(resource.used_raw, resource.limit_raw)
        used = round(resource.used_raw / resource.divisor, 2)
        limit = (
            round(resource.limit_raw / resource.divisor, 2)
            if resource.limit_raw is not None
            else None
        )
        remaining = max((limit or 0) - used, 0) if limit is not None else None
        percentage = (
            round(min(resource.used_raw / resource.limit_raw * 100, 100), 1)
            if resource.limit_raw and resource.limit_raw > 0
            else (100.0 if resource.limit_raw == 0 else None)
        )
        if state not in {"OK", "UNLIMITED"}:
            messages = {
                "WARNING": f"{resource.label} usage has reached 80% of the plan limit.",
                "HIGH_USAGE": f"{resource.label} usage has reached 90% of the plan limit.",
                "LIMIT_REACHED": f"{resource.label} limit reached. Upgrade recommended.",
            }
            self.repository.sync_alert(snapshot.company_id, resource.code, state, messages[state])
        else:
            self.repository.sync_alert(snapshot.company_id, resource.code, state, "")
        return UsageMetricResponse(
            code=resource.code,
            label=resource.label,
            used=used,
            limit=limit,
            remaining=remaining,
            percentage=percentage,
            state=state,
            unit=resource.unit,
            upgrade_recommended=state == "LIMIT_REACHED",
        )

    def usage(self, context: AuthContext, company_id: UUID) -> CompanyUsageResponse:
        self._authorize(context)
        snapshot = self._snapshot(company_id)
        metrics = [self._metric(snapshot, item) for item in self._resources(snapshot)]
        alerts = [
            UsageAlertResponse(
                resource_code=item.code,
                level=item.state,
                message=(
                    f"{item.label} limit reached. Upgrade recommended."
                    if item.state == "LIMIT_REACHED"
                    else f"{item.label} usage is approaching the plan limit."
                ),
            )
            for item in metrics
            if item.state not in {"OK", "UNLIMITED"}
        ]
        self.repository.record_event(
            company_id, context.user_id, snapshot.plan_id, "PLAN_VALIDATED", None
        )
        return CompanyUsageResponse(
            company_id=company_id,
            company_name=snapshot.company_name,
            plan_id=snapshot.plan_id,
            plan_name=snapshot.plan_name,
            plan_code=snapshot.plan_code,
            features=snapshot.features,
            usage=metrics,
            alerts=alerts,
            upgrade_recommended=any(item.upgrade_recommended for item in metrics),
        )

    def validate(
        self,
        context: AuthContext,
        company_id: UUID,
        request: SubscriptionValidationRequest,
    ) -> SubscriptionEnforcementResponse:
        self._authorize(context)
        if request.feature_code:
            return self.validate_feature(company_id, request.feature_code, context.user_id)
        return self.validate_limit(
            company_id,
            request.resource_code or "",
            request.requested_increment,
            context.user_id,
        )

    def validate_feature(
        self, company_id: UUID, feature_code: str, actor_id: UUID | None = None
    ) -> SubscriptionEnforcementResponse:
        snapshot = self._snapshot(company_id)
        allowed = bool(snapshot.features.get(feature_code, False))
        self.repository.record_event(
            company_id,
            actor_id,
            snapshot.plan_id,
            "PLAN_VALIDATED" if allowed else "FEATURE_BLOCKED",
            feature_code,
            details="Feature enabled" if allowed else "Feature is unavailable on the current plan",
        )
        return SubscriptionEnforcementResponse(
            company_id=company_id,
            plan_code=snapshot.plan_code,
            validation_type="FEATURE",
            code=feature_code,
            allowed=allowed,
            reason="Feature is available." if allowed else "Feature is not available on this plan.",
            upgrade_recommended=not allowed,
        )

    def validate_limit(
        self,
        company_id: UUID,
        resource_code: str,
        requested_increment: int = 1,
        actor_id: UUID | None = None,
    ) -> SubscriptionEnforcementResponse:
        snapshot = self._snapshot(company_id)
        resource = next(
            (item for item in self._resources(snapshot) if item.code == resource_code), None
        )
        if not resource:
            raise AuthenticationError(
                422, "UNKNOWN_LIMIT", "The requested usage limit is not configured."
            )
        state = self._state(resource.used_raw, resource.limit_raw)
        allowed = (
            resource.limit_raw is None
            or resource.used_raw + requested_increment <= resource.limit_raw
        )
        response_state = state if allowed else "LIMIT_REACHED"
        if not allowed:
            self.repository.record_event(
                company_id,
                actor_id,
                snapshot.plan_id,
                "LIMIT_EXCEEDED",
                resource_code,
                resource.used_raw,
                resource.limit_raw,
                "Requested operation exceeds the configured plan limit",
            )
            self.repository.record_event(
                company_id,
                actor_id,
                snapshot.plan_id,
                "UPGRADE_RECOMMENDED",
                resource_code,
                resource.used_raw,
                resource.limit_raw,
            )
            self.repository.sync_alert(
                company_id,
                resource_code,
                "LIMIT_REACHED",
                f"{resource.label} limit reached. Upgrade recommended.",
            )
        else:
            self.repository.sync_alert(company_id, resource_code, response_state, "")
        divisor = resource.divisor
        used = round(resource.used_raw / divisor, 2)
        limit = round(resource.limit_raw / divisor, 2) if resource.limit_raw is not None else None
        return SubscriptionEnforcementResponse(
            company_id=company_id,
            plan_code=snapshot.plan_code,
            validation_type="LIMIT",
            code=resource_code,
            allowed=allowed,
            reason=(
                "Usage is within the plan limit."
                if allowed
                else "Plan limit reached. Upgrade recommended."
            ),
            used=used,
            limit=limit,
            remaining=max((limit or 0) - used, 0) if limit is not None else None,
            unlimited=resource.limit_raw is None,
            state=response_state,
            upgrade_recommended=not allowed,
        )

    def enforce_limit(
        self,
        company_id: UUID,
        resource_code: str,
        requested_increment: int = 1,
        actor_id: UUID | None = None,
    ) -> None:
        result = self.validate_limit(company_id, resource_code, requested_increment, actor_id)
        if not result.allowed:
            raise AuthenticationError(403, "SUBSCRIPTION_LIMIT_REACHED", result.reason)

    def is_ready(self) -> bool:
        return self.repository.is_ready()


subscription_enforcement_service = SubscriptionEnforcementService()
