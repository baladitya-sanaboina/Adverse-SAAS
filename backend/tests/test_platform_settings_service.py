import unittest
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from app.repositories.platform_settings_repository import PlatformSettingsRecord
from app.schemas.authentication import AuthContext
from app.schemas.platform_settings import MaintenanceSettingsUpdate, SmtpSettingsUpdate
from app.services.authentication_service import AuthenticationError
from app.services.platform_settings_service import PlatformSettingsService


def record() -> PlatformSettingsRecord:
    now = datetime.now(UTC)
    return PlatformSettingsRecord(
        id="global",
        platform_name="Adverse",
        platform_logo_url=None,
        favicon_url=None,
        primary_color="#0876ED",
        secondary_color="#065EC1",
        footer_text="© Adverse",
        support_email="support@adverse.example.com",
        support_phone=None,
        default_timezone="UTC",
        default_language="en",
        default_company_status="ACTIVE",
        default_user_status="PENDING_VERIFICATION",
        default_subscription_code="STARTER",
        smtp_host="mailpit",
        smtp_port=1025,
        smtp_username="",
        smtp_password_encrypted="",
        smtp_encryption="NONE",
        smtp_sender_name="Adverse",
        smtp_sender_email="no-reply@adverse.example.com",
        maintenance_enabled=False,
        maintenance_message="Adverse is temporarily unavailable for scheduled maintenance.",
        maintenance_allowed_roles=["PLATFORM_OWNER"],
        created_at=now,
        updated_at=now,
    )


class FakeRepository:
    def __init__(self) -> None:
        self.value = record()
        self.actions: list[str] = []

    def get(self) -> PlatformSettingsRecord:
        return self.value

    def update(self, _actor_id, values, action):  # type: ignore[no-untyped-def]
        self.actions.append(action)
        self.value = replace(self.value, **values, updated_at=datetime.now(UTC))
        return self.value

    def audit(self, _actor_id, action):  # type: ignore[no-untyped-def]
        self.actions.append(action)

    def is_ready(self) -> bool:
        return True


def context(role: str = "PLATFORM_OWNER") -> AuthContext:
    now = datetime.now(UTC)
    return AuthContext(
        user_id=uuid4(),
        role=role,
        company_id=None,
        user_type="platform",
        session_id=uuid4(),
        issued_at=now,
        expires_at=now,
    )


class PlatformSettingsServiceTests(unittest.TestCase):
    def test_settings_are_masked_and_platform_owner_only(self) -> None:
        repository = FakeRepository()
        service = PlatformSettingsService(repository)  # type: ignore[arg-type]
        response = service.get(context())
        self.assertFalse(response.smtp.password_configured)
        self.assertNotIn("password", response.model_dump()["smtp"])
        with self.assertRaises(AuthenticationError) as denied:
            service.get(context("DEVELOPER"))
        self.assertEqual(denied.exception.status_code, 403)

    def test_smtp_password_is_encrypted_and_never_returned(self) -> None:
        repository = FakeRepository()
        service = PlatformSettingsService(repository)  # type: ignore[arg-type]
        response = service.update_smtp(
            context(),
            SmtpSettingsUpdate(
                host="mailpit",
                port=1025,
                username="mailer",
                password="secret-value",
                encryption="NONE",
                sender_name="Adverse",
                sender_email="mail@adverse.in",
            ),
        )
        encrypted = repository.value.smtp_password_encrypted
        self.assertTrue(encrypted and "secret-value" not in encrypted)
        self.assertEqual(service.decrypt_password(encrypted), "secret-value")
        self.assertTrue(response.smtp.password_configured)
        self.assertEqual(repository.actions, ["SMTP_UPDATED"])

    def test_maintenance_keeps_platform_owner_access(self) -> None:
        repository = FakeRepository()
        service = PlatformSettingsService(repository)  # type: ignore[arg-type]
        response = service.update_maintenance(
            context(),
            MaintenanceSettingsUpdate(
                enabled=True,
                message="Scheduled maintenance is currently in progress.",
                allowed_roles=["PLATFORM_OWNER", "DEVELOPER"],
            ),
        )
        self.assertTrue(response.maintenance.enabled)
        self.assertEqual(response.maintenance.allowed_roles, ["PLATFORM_OWNER", "DEVELOPER"])
        self.assertEqual(repository.actions, ["MAINTENANCE_ENABLED"])

    def test_platform_owner_cannot_be_removed_from_maintenance_access(self) -> None:
        with self.assertRaises(ValueError):
            MaintenanceSettingsUpdate(
                enabled=True,
                message="Scheduled maintenance is currently in progress.",
                allowed_roles=["DEVELOPER"],
            )
