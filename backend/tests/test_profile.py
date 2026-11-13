import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from pydantic import ValidationError

from app.repositories.profile_repository import ProfileDetailsRecord
from app.schemas.authentication import AuthContext
from app.schemas.current_user import CurrentUserResponse
from app.schemas.profile import ChangePasswordRequest, UpdateProfileRequest
from app.services.authentication_service import AuthenticationError
from app.services.password_service import hash_password, verify_password
from app.services.profile_service import ProfileService


class FakeProfileRepository:
    def __init__(self) -> None:
        self.details = ProfileDetailsRecord(
            "Adverse",
            "User",
            "+91 98765 43210",
            None,
            "UTC",
            "en",
            "system",
            True,
            hash_password("CurrentPass!123"),
        )
        self.audit_actions: list[str] = []
        self.sessions_revoked = False

    def load_details(self, user_id):
        return self.details

    def update_profile(self, user_id, company_id, values):
        self.details = ProfileDetailsRecord(
            values["first_name"],
            values["last_name"],
            values["phone_number"],
            self.details.profile_image_url,
            values["timezone"],
            values["language"],
            values["theme_preference"],
            values["email_notifications"],
            self.details.password_hash,
        )
        self.audit_actions.append("PROFILE_UPDATED")
        return True

    def change_password(self, user_id, company_id, password_hash):
        raise NotImplementedError

    def update_image(self, user_id, company_id, url):
        self.details = ProfileDetailsRecord(
            self.details.first_name,
            self.details.last_name,
            self.details.phone_number,
            url,
            self.details.timezone,
            self.details.language,
            self.details.theme_preference,
            self.details.email_notifications,
            self.details.password_hash,
        )
        self.audit_actions.append("PROFILE_IMAGE_UPDATED")
        return True

    def foundation_is_ready(self):
        return True


class FakeCurrentUsers:
    def __init__(self, context: AuthContext) -> None:
        self.context = context

    def get_current_user(self, context: AuthContext) -> CurrentUserResponse:
        return CurrentUserResponse.model_validate(
            {
                "user": {
                    "id": context.user_id,
                    "name": "Adverse User",
                    "email": "profile@loopless.in",
                    "status": "ACTIVE",
                    "created_at": datetime.now(UTC),
                },
                "company": None,
                "role": {"id": uuid4(), "name": "Developer", "code": "DEVELOPER"},
                "permissions": [],
            }
        )


class WorkingProfileRepository(FakeProfileRepository):
    def change_password(self, user_id, company_id, password_hash):
        self.details = ProfileDetailsRecord(
            self.details.first_name,
            self.details.last_name,
            self.details.phone_number,
            self.details.profile_image_url,
            self.details.timezone,
            self.details.language,
            self.details.theme_preference,
            self.details.email_notifications,
            password_hash,
        )
        self.sessions_revoked = True
        self.audit_actions.append("PASSWORD_CHANGED")
        return True


class ProfileServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        now = datetime.now(UTC)
        self.context = AuthContext(
            user_id=uuid4(),
            role="DEVELOPER",
            company_id=None,
            user_type="platform",
            session_id=uuid4(),
            issued_at=now,
            expires_at=now,
        )
        self.repository = WorkingProfileRepository()
        self.service = ProfileService(self.repository, FakeCurrentUsers(self.context))

    def test_get_and_update_own_profile_and_preferences(self):
        profile = self.service.get_profile(self.context)
        self.assertEqual(profile.user.email, "profile@loopless.in")
        updated = self.service.update_profile(
            self.context,
            UpdateProfileRequest(
                first_name="Updated",
                last_name="User",
                phone_number="+91 90000 00000",
                timezone="Asia/Kolkata",
                language="te",
                theme_preference="dark",
                email_notifications=False,
            ),
        )
        self.assertEqual(updated.first_name, "Updated")
        self.assertEqual(updated.settings.timezone, "Asia/Kolkata")
        self.assertIn("PROFILE_UPDATED", self.repository.audit_actions)

    def test_role_company_permissions_and_status_cannot_be_updated(self):
        with self.assertRaises(ValidationError):
            UpdateProfileRequest.model_validate(
                {
                    "first_name": "User",
                    "role": "PLATFORM_OWNER",
                    "company_id": str(uuid4()),
                    "permissions": ["MANAGE"],
                    "status": "SUSPENDED",
                }
            )

    def test_password_change_validates_current_hashes_new_and_revokes_sessions(self):
        with self.assertRaisesRegex(AuthenticationError, "incorrect"):
            self.service.change_password(
                self.context,
                ChangePasswordRequest(
                    current_password="WrongPass!123",
                    new_password="NewStrongPass!123",
                    confirm_password="NewStrongPass!123",
                ),
            )
        self.service.change_password(
            self.context,
            ChangePasswordRequest(
                current_password="CurrentPass!123",
                new_password="NewStrongPass!123",
                confirm_password="NewStrongPass!123",
            ),
        )
        self.assertTrue(verify_password("NewStrongPass!123", self.repository.details.password_hash))
        self.assertTrue(self.repository.sessions_revoked)
        self.assertIn("PASSWORD_CHANGED", self.repository.audit_actions)

    def test_image_upload_validates_type_size_and_file_signature(self):
        with self.assertRaisesRegex(AuthenticationError, "JPG"):
            self.service.upload_image(self.context, "text/plain", b"plain text")
        with self.assertRaisesRegex(AuthenticationError, "content"):
            self.service.upload_image(self.context, "image/png", b"not-a-png")
        with tempfile.TemporaryDirectory() as directory:
            with patch("app.services.profile_service.PROFILE_IMAGE_DIRECTORY", Path(directory)):
                response = self.service.upload_image(
                    self.context,
                    "image/png",
                    b"\x89PNG\r\n\x1a\nvalid-image-data",
                )
                self.assertTrue((Path(directory) / Path(response.profile_image_url).name).exists())
        self.assertIn("PROFILE_IMAGE_UPDATED", self.repository.audit_actions)


if __name__ == "__main__":
    unittest.main()
