from pathlib import Path
from uuid import uuid4

from app.repositories.profile_repository import ProfileRepository
from app.schemas.authentication import AuthContext
from app.schemas.profile import (
    ChangePasswordRequest,
    ProfileImageResponse,
    ProfileMessageResponse,
    ProfileResponse,
    ProfileSettings,
    UpdateProfileRequest,
)
from app.services.authentication_service import AuthenticationError
from app.services.current_user_service import CurrentUserService, current_user_service
from app.services.password_service import hash_password, verify_password

ALLOWED_IMAGE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
MAX_IMAGE_SIZE = 5 * 1024 * 1024
PROFILE_IMAGE_DIRECTORY = Path("storage/profile-images")


def image_matches_type(content_type: str, content: bytes) -> bool:
    if content_type == "image/jpeg":
        return content.startswith(b"\xff\xd8\xff")
    if content_type == "image/png":
        return content.startswith(b"\x89PNG\r\n\x1a\n")
    if content_type == "image/webp":
        return len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP"
    return False


class ProfileService:
    def __init__(
        self, repository: ProfileRepository | None = None, users: CurrentUserService | None = None
    ):
        self.repository = repository or ProfileRepository()
        self.users = users or current_user_service

    def get_profile(self, context: AuthContext) -> ProfileResponse:
        user = self.users.get_current_user(context)
        details = self.repository.load_details(context.user_id)
        if details is None:
            raise AuthenticationError(404, "PROFILE_NOT_FOUND", "Profile does not exist.")
        return ProfileResponse(
            **user.model_dump(),
            first_name=details.first_name,
            last_name=details.last_name,
            phone_number=details.phone_number,
            profile_image_url=details.profile_image_url,
            settings=ProfileSettings(
                timezone=details.timezone,
                language=details.language,
                theme_preference=details.theme_preference,
                email_notifications=details.email_notifications,
            ),
        )

    def update_profile(
        self, context: AuthContext, request: UpdateProfileRequest
    ) -> ProfileResponse:
        self.users.get_current_user(context)
        values = request.model_dump()
        if not self.repository.update_profile(context.user_id, context.company_id, values):
            raise AuthenticationError(404, "PROFILE_NOT_FOUND", "Profile does not exist.")
        return self.get_profile(context)

    def change_password(
        self, context: AuthContext, request: ChangePasswordRequest
    ) -> ProfileMessageResponse:
        self.users.get_current_user(context)
        details = self.repository.load_details(context.user_id)
        if details is None or not verify_password(
            request.current_password.get_secret_value(), details.password_hash
        ):
            raise AuthenticationError(
                400, "INVALID_CURRENT_PASSWORD", "Current password is incorrect."
            )
        if verify_password(request.new_password.get_secret_value(), details.password_hash):
            raise AuthenticationError(400, "PASSWORD_UNCHANGED", "New password must be different.")
        if not self.repository.change_password(
            context.user_id,
            context.company_id,
            hash_password(request.new_password.get_secret_value()),
        ):
            raise AuthenticationError(404, "PROFILE_NOT_FOUND", "Profile does not exist.")
        return ProfileMessageResponse(message="Password changed successfully. Sign in again.")

    def upload_image(
        self, context: AuthContext, content_type: str, content: bytes
    ) -> ProfileImageResponse:
        self.users.get_current_user(context)
        extension = ALLOWED_IMAGE_TYPES.get(content_type)
        if extension is None:
            raise AuthenticationError(400, "INVALID_IMAGE_TYPE", "Use a JPG, PNG, or WEBP image.")
        if not content or len(content) > MAX_IMAGE_SIZE:
            raise AuthenticationError(
                400, "INVALID_IMAGE_SIZE", "Profile image must be between 1 byte and 5 MB."
            )
        if not image_matches_type(content_type, content):
            raise AuthenticationError(
                400,
                "INVALID_IMAGE_CONTENT",
                "The uploaded file content does not match its image type.",
            )
        PROFILE_IMAGE_DIRECTORY.mkdir(parents=True, exist_ok=True)
        filename = f"{context.user_id}-{uuid4().hex}{extension}"
        destination = PROFILE_IMAGE_DIRECTORY / filename
        destination.write_bytes(content)
        url = f"/storage/profile-images/{filename}"
        if not self.repository.update_image(context.user_id, context.company_id, url):
            destination.unlink(missing_ok=True)
            raise AuthenticationError(404, "PROFILE_NOT_FOUND", "Profile does not exist.")
        return ProfileImageResponse(profile_image_url=url)

    def is_ready(self) -> bool:
        return self.repository.foundation_is_ready()


profile_service = ProfileService()
