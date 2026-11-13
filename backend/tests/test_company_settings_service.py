import unittest
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from app.repositories.company_settings_repository import CompanySettingsRecord
from app.schemas.authentication import AuthContext
from app.schemas.company_settings import CompanySettingsUpdate
from app.services.authentication_service import AuthenticationError
from app.services.company_settings_service import CompanySettingsService


def settings_record(company_id: str | None = None) -> CompanySettingsRecord:
    return CompanySettingsRecord(
        company_id=company_id or str(uuid4()),
        company_code="LOOP-001",
        company_name="Adverse Company",
        description="Tenant profile",
        business_email="admin@company.example",
        phone=None,
        address=None,
        website=None,
        timezone="UTC",
        language="en",
        logo_url=None,
        favicon_url=None,
        primary_color="#0876ED",
        secondary_color="#065EC1",
        email_footer="",
        support_email=None,
        support_phone=None,
        gst_tax_id=None,
        registration_number=None,
        currency="USD",
        date_format="DD/MM/YYYY",
        time_format="12_HOUR",
        working_days=["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY"],
        business_hours={"start": "09:00", "end": "18:00"},
        theme="system",
        notifications={"email": True, "system": True, "maintenance": True, "security": True},
        updated_at=datetime.now(UTC),
    )


class FakeRepository:
    def __init__(self) -> None:
        self.value = settings_record()
        self.actions: list[str] = []
        self.requested_companies: list[str] = []

    def get(self, company_id):  # type: ignore[no-untyped-def]
        self.requested_companies.append(str(company_id))
        return self.value if str(company_id) == self.value.company_id else None

    def update(self, actor_id, company_id, company_values, default_values, actions):  # type: ignore[no-untyped-def]
        del actor_id
        self.requested_companies.append(str(company_id))
        self.actions.extend(actions)
        values = {
            "company_name": company_values.get("name", self.value.company_name),
            "description": company_values.get("description", self.value.description),
            "business_email": company_values.get("contact_email", self.value.business_email),
            "phone": company_values.get("phone", self.value.phone),
            "address": company_values.get("address", self.value.address),
            "website": company_values.get("website", self.value.website),
            "timezone": company_values.get("timezone", self.value.timezone),
            "language": company_values.get("language", self.value.language),
            "updated_at": datetime.now(UTC),
        }
        mapping = {
            "logo_url": "logo_url",
            "favicon_url": "favicon_url",
            "primary_color": "primary_color",
            "secondary_color": "secondary_color",
            "email_footer": "email_footer",
            "support_email": "support_email",
            "support_phone": "support_phone",
            "gst_tax_id": "gst_tax_id",
            "registration_number": "registration_number",
            "currency": "currency",
            "date_format": "date_format",
            "time_format": "time_format",
            "working_days": "working_days",
            "business_hours": "business_hours",
            "theme": "theme",
            "notification_preferences": "notifications",
        }
        values.update(
            {mapping[key]: value for key, value in default_values.items() if key in mapping}
        )
        self.value = replace(self.value, **values)
        return self.value

    def is_ready(self) -> bool:
        return True


def context(role: str = "COMPANY_ADMIN", company_id=None) -> AuthContext:  # type: ignore[no-untyped-def]
    now = datetime.now(UTC)
    return AuthContext(
        user_id=uuid4(),
        role=role,
        company_id=company_id or uuid4(),
        user_type="company" if role.startswith("COMPANY_") else "platform",
        session_id=uuid4(),
        issued_at=now,
        expires_at=now,
    )


class CompanySettingsServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = FakeRepository()
        self.service = CompanySettingsService(self.repository)  # type: ignore[arg-type]
        self.admin = context(company_id=self.repository.value.company_id)

    def test_company_admin_reads_only_token_company(self) -> None:
        response = self.service.get(self.admin)
        self.assertEqual(response.company_id, self.repository.value.company_id)
        self.assertEqual(self.repository.requested_companies, [self.repository.value.company_id])

    def test_other_roles_cannot_read_or_update(self) -> None:
        for role in ("COMPANY_EMPLOYEE", "COMPANY_CLIENT", "DEVELOPER", "PLATFORM_OWNER"):
            with self.assertRaises(AuthenticationError) as denied:
                self.service.get(context(role))
            self.assertEqual(denied.exception.status_code, 403)

    def test_company_roles_read_only_their_tenant_branding(self) -> None:
        for role in ("COMPANY_ADMIN", "COMPANY_MANAGER", "COMPANY_EMPLOYEE", "COMPANY_CLIENT"):
            branding = self.service.branding(
                context(role, company_id=self.repository.value.company_id)
            )
            self.assertEqual(branding.company_id, self.repository.value.company_id)
            self.assertEqual(branding.primary_color, "#0876ED")
        with self.assertRaises(AuthenticationError) as denied:
            self.service.branding(context("DEVELOPER"))
        self.assertEqual(denied.exception.status_code, 403)

    def test_update_persists_groups_and_writes_audits(self) -> None:
        current = self.service.get(self.admin)
        payload = CompanySettingsUpdate(
            general={"company_name": "Updated Tenant", "description": "Updated profile"},
            branding={**current.branding.model_dump(), "primary_color": "#123456"},
            contact={**current.contact.model_dump(), "support_email": "support@tenant.example"},
            regional={
                **current.regional.model_dump(),
                "currency": "INR",
                "timezone": "Asia/Kolkata",
            },
            notifications={**current.notifications.model_dump(), "maintenance": False},
            preferences={**current.preferences.model_dump(), "theme": "dark"},
        )
        response = self.service.update(self.admin, payload)
        self.assertEqual(response.general.company_name, "Updated Tenant")
        self.assertEqual(response.general.description, "Updated profile")
        self.assertEqual(response.regional.currency, "INR")
        self.assertEqual(response.preferences.theme, "dark")
        self.assertIn("COMPANY_SETTINGS_UPDATED", self.repository.actions)
        self.assertIn("COMPANY_BRANDING_UPDATED", self.repository.actions)
        self.assertIn("COMPANY_REGIONAL_UPDATED", self.repository.actions)
        self.assertIn("COMPANY_PREFERENCES_UPDATED", self.repository.actions)

    def test_invalid_business_hours_are_rejected(self) -> None:
        current = self.service.get(self.admin)
        payload = current.model_dump(exclude={"company_id", "company_code", "updated_at"})
        payload["preferences"]["business_hours_start"] = "18:00"
        payload["preferences"]["business_hours_end"] = "09:00"
        with self.assertRaises(ValueError):
            CompanySettingsUpdate.model_validate(payload)

    def test_logo_removal_is_tenant_scoped_and_audited(self) -> None:
        self.repository.value = replace(
            self.repository.value,
            logo_url=f"/storage/company-branding/{self.repository.value.company_id}/logo.png",
        )
        response = self.service.remove(self.admin, "logo")
        self.assertIsNone(response.url)
        self.assertIsNone(self.repository.value.logo_url)
        self.assertIn("COMPANY_LOGO_UPDATED", self.repository.actions)

    def test_invalid_contact_and_timezone_are_rejected(self) -> None:
        current = self.service.get(self.admin)
        payload = current.model_dump(exclude={"company_id", "company_code", "updated_at"})
        payload["contact"]["phone"] = "invalid-phone"
        payload["regional"]["timezone"] = "Not/A_Timezone"
        with self.assertRaises(ValueError):
            CompanySettingsUpdate.model_validate(payload)


if __name__ == "__main__":
    unittest.main()
