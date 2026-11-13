import unittest
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

from app.repositories.subscription_management_repository import CompanyPlanRecord, PlanRecord
from app.schemas.authentication import AuthContext
from app.schemas.subscription_management import (
    CompanyPlanAssignmentRequest,
    PlanCreateRequest,
    PlanListFilters,
    PlanUpdateRequest,
)
from app.services.authentication_service import AuthenticationError
from app.services.subscription_management_service import SubscriptionManagementService


class FakeSubscriptionRepository:
    def __init__(self):
        now = datetime.now(UTC)
        self.plan = PlanRecord(
            uuid4(),
            "Professional",
            "PROFESSIONAL",
            "Growing teams",
            Decimal("79"),
            Decimal("790"),
            "ACTIVE",
            2,
            {"CRM": True, "WHITE_LABEL": False},
            {"MAX_EMPLOYEES": 150, "MAX_PROJECTS": None},
            1,
            now,
            now,
        )
        self.company_id = uuid4()

    def code_exists(self, code, exclude_id=None):
        return code == self.plan.code

    def create_plan(self, actor_id, payload):
        return PlanRecord(
            uuid4(),
            payload.name,
            payload.code,
            payload.description,
            payload.monthly_price,
            payload.yearly_price,
            payload.status,
            payload.display_order,
            payload.features,
            payload.limits,
            0,
            datetime.now(UTC),
            datetime.now(UTC),
        )

    def list_plans(self, filters):
        return ((self.plan,), 1)

    def get_plan(self, plan_id):
        return self.plan if plan_id == self.plan.id else None

    def get_company_plan(self, company_id):
        return self.plan if company_id == self.company_id else None

    def update_plan(self, actor_id, plan_id, payload):
        if plan_id != self.plan.id:
            return None
        self.plan = PlanRecord(
            **{
                **self.plan.__dict__,
                "name": payload.name,
                "status": payload.status,
                "features": payload.features,
                "limits": payload.limits,
            }
        )
        return self.plan

    def assign_plan(self, actor_id, company_id, plan_id, activation_date, expiration_date):
        if company_id != self.company_id or plan_id != self.plan.id:
            return None
        return CompanyPlanRecord(
            company_id,
            "Acme",
            self.plan,
            "ACTIVE",
            activation_date,
            expiration_date,
            1,
        )

    def is_ready(self):
        return True


class SubscriptionManagementTests(unittest.TestCase):
    def setUp(self):
        self.repository = FakeSubscriptionRepository()
        self.service = SubscriptionManagementService(self.repository)
        now = datetime.now(UTC)
        self.context = AuthContext(
            user_id=uuid4(),
            role="PLATFORM_OWNER",
            company_id=None,
            user_type="platform",
            session_id=uuid4(),
            issued_at=now,
            expires_at=now + timedelta(minutes=30),
        )

    @patch(
        "app.services.subscription_management_service.validate_user_action_access",
        return_value=True,
    )
    def test_create_list_update_and_assign(self, _permission):
        created = self.service.create(
            self.context,
            PlanCreateRequest(name="Starter", code="STARTER", features={"CRM": True}),
        )
        self.assertEqual(created.code, "STARTER")
        self.assertEqual(self.service.list(self.context, PlanListFilters()).total, 1)
        updated = self.service.update(
            self.context,
            self.repository.plan.id,
            PlanUpdateRequest(
                name="Professional Plus",
                status="ACTIVE",
                features={"CRM": True},
                limits={"MAX_PROJECTS": None},
            ),
        )
        self.assertEqual(updated.name, "Professional Plus")
        assignment = self.service.assign(
            self.context,
            self.repository.company_id,
            CompanyPlanAssignmentRequest(plan_id=self.repository.plan.id),
        )
        self.assertEqual(assignment.change_type, "UPGRADE")

    @patch(
        "app.services.subscription_management_service.validate_user_action_access",
        return_value=True,
    )
    def test_duplicate_and_period_validation(self, _permission):
        with self.assertRaises(AuthenticationError) as duplicate:
            self.service.create(
                self.context,
                PlanCreateRequest(name="Professional", code="PROFESSIONAL"),
            )
        self.assertEqual(duplicate.exception.status_code, 409)
        now = datetime.now(UTC)
        with self.assertRaises(AuthenticationError) as invalid_period:
            self.service.assign(
                self.context,
                self.repository.company_id,
                CompanyPlanAssignmentRequest(
                    plan_id=self.repository.plan.id,
                    activation_date=now,
                    expiration_date=now - timedelta(days=1),
                ),
            )
        self.assertEqual(invalid_period.exception.status_code, 422)

    def test_validation_uses_current_company_plan(self):
        allowed = self.service.validate(self.repository.company_id, feature_code="CRM")
        denied = self.service.validate(self.repository.company_id, feature_code="WHITE_LABEL")
        unlimited = self.service.validate(self.repository.company_id, limit_code="MAX_PROJECTS")
        self.assertTrue(allowed.allowed)
        self.assertFalse(denied.allowed)
        self.assertTrue(unlimited.unlimited)

    @patch(
        "app.services.subscription_management_service.validate_user_action_access",
        return_value=False,
    )
    def test_manage_permission_is_required(self, _permission):
        with self.assertRaises(AuthenticationError) as denied:
            self.service.list(self.context, PlanListFilters())
        self.assertEqual(denied.exception.status_code, 403)

    def test_actions_use_granular_permissions(self):
        with patch(
            "app.services.subscription_management_service.validate_user_action_access",
            return_value=True,
        ) as permission:
            self.service.list(self.context, PlanListFilters())
            permission.assert_called_with(
                str(self.context.user_id), "PLATFORM_OWNER", "SUBSCRIPTIONS", "VIEW"
            )

    def test_update_rejects_protected_plan_code(self):
        with self.assertRaises(ValueError):
            PlanUpdateRequest.model_validate(
                {
                    "name": "Professional",
                    "code": "STARTER",
                    "features": {},
                    "limits": {},
                }
            )


if __name__ == "__main__":
    unittest.main()
