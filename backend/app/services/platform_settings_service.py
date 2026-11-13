import base64
import hashlib
import smtplib
from email.message import EmailMessage
from pathlib import Path
from typing import Literal, cast
from uuid import uuid4

from cryptography.fernet import Fernet, InvalidToken
from fastapi import UploadFile

from app.core.settings import settings
from app.repositories.platform_settings_repository import (
    PlatformSettingsRecord,
    PlatformSettingsRepository,
)
from app.schemas.authentication import AuthContext
from app.schemas.platform_settings import (
    ActionResponse,
    BrandingAssetResponse,
    MaintenanceSettingsResponse,
    MaintenanceSettingsUpdate,
    PlatformSettingsResponse,
    PlatformSettingsUpdate,
    PublicMaintenanceResponse,
    SmtpSettingsResponse,
    SmtpSettingsUpdate,
)
from app.services.authentication_service import AuthenticationError
from app.services.email_service import branded_email_html


class PlatformSettingsService:
    _upload_root = Path("storage/platform-branding")
    _mime_extensions = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/webp": ".webp",
        "image/x-icon": ".ico",
        "image/vnd.microsoft.icon": ".ico",
    }
    _image_signatures = {
        ".png": lambda content: content.startswith(b"\x89PNG\r\n\x1a\n"),
        ".jpg": lambda content: content.startswith(b"\xff\xd8\xff"),
        ".webp": lambda content: content.startswith(b"RIFF") and content[8:12] == b"WEBP",
        ".ico": lambda content: content.startswith(b"\x00\x00\x01\x00"),
    }

    def __init__(self, repository: PlatformSettingsRepository | None = None):
        self.repository = repository or PlatformSettingsRepository()

    @staticmethod
    def _authorize(context: AuthContext) -> None:
        if context.role != "PLATFORM_OWNER":
            raise AuthenticationError(
                403, "PLATFORM_OWNER_REQUIRED", "Only the Platform Owner can manage settings."
            )

    @staticmethod
    def _fernet() -> Fernet:
        digest = hashlib.sha256(settings.jwt_secret.get_secret_value().encode()).digest()
        return Fernet(base64.urlsafe_b64encode(digest))

    def _encrypt(self, value: str) -> str:
        return self._fernet().encrypt(value.encode()).decode() if value else ""

    def decrypt_password(self, value: str) -> str:
        if not value:
            return ""
        try:
            return self._fernet().decrypt(value.encode()).decode()
        except InvalidToken as error:
            raise RuntimeError("Stored SMTP credentials cannot be decrypted.") from error

    def _smtp_status(self, record: PlatformSettingsRecord) -> Literal["connected", "unavailable"]:
        client: smtplib.SMTP | None = None
        try:
            client = self._smtp_connection(record)
            return "connected" if client.noop()[0] == 250 else "unavailable"
        except (OSError, smtplib.SMTPException, RuntimeError):
            return "unavailable"
        finally:
            if client is not None:
                client.close()

    def _response(self, record: PlatformSettingsRecord) -> PlatformSettingsResponse:
        return PlatformSettingsResponse(
            id=record.id,
            platform_name=record.platform_name,
            platform_logo_url=record.platform_logo_url,
            favicon_url=record.favicon_url,
            primary_color=record.primary_color,
            secondary_color=record.secondary_color,
            footer_text=record.footer_text,
            support_email=record.support_email,
            support_phone=record.support_phone,
            default_timezone=record.default_timezone,
            default_language=record.default_language,
            default_company_status=record.default_company_status,
            default_user_status=record.default_user_status,
            default_subscription_code=record.default_subscription_code,
            smtp=SmtpSettingsResponse(
                host=record.smtp_host,
                port=record.smtp_port,
                username=record.smtp_username,
                encryption=record.smtp_encryption,
                sender_name=record.smtp_sender_name,
                sender_email=record.smtp_sender_email,
                password_configured=bool(record.smtp_password_encrypted),
                connection_status=self._smtp_status(record),
            ),
            maintenance=MaintenanceSettingsResponse(
                enabled=record.maintenance_enabled,
                message=record.maintenance_message,
                allowed_roles=record.maintenance_allowed_roles,
            ),
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    def get(self, context: AuthContext) -> PlatformSettingsResponse:
        self._authorize(context)
        return self._response(self.repository.get())

    def update(
        self, context: AuthContext, request: PlatformSettingsUpdate
    ) -> PlatformSettingsResponse:
        self._authorize(context)
        values = request.model_dump()
        return self._response(self.repository.update(context.user_id, values, "SETTINGS_UPDATED"))

    def update_smtp(
        self, context: AuthContext, request: SmtpSettingsUpdate
    ) -> PlatformSettingsResponse:
        self._authorize(context)
        values = {
            "smtp_host": request.host,
            "smtp_port": request.port,
            "smtp_username": request.username,
            "smtp_encryption": request.encryption,
            "smtp_sender_name": request.sender_name,
            "smtp_sender_email": str(request.sender_email),
        }
        if request.password is not None:
            values["smtp_password_encrypted"] = self._encrypt(request.password.get_secret_value())
        return self._response(self.repository.update(context.user_id, values, "SMTP_UPDATED"))

    def update_maintenance(
        self, context: AuthContext, request: MaintenanceSettingsUpdate
    ) -> PlatformSettingsResponse:
        self._authorize(context)
        action = "MAINTENANCE_ENABLED" if request.enabled else "MAINTENANCE_DISABLED"
        return self._response(
            self.repository.update(
                context.user_id,
                {
                    "maintenance_enabled": request.enabled,
                    "maintenance_message": request.message,
                    "maintenance_allowed_roles": request.allowed_roles,
                },
                action,
            )
        )

    def public_maintenance(self) -> PublicMaintenanceResponse:
        record = self.repository.get()
        return PublicMaintenanceResponse(
            enabled=record.maintenance_enabled, message=record.maintenance_message
        )

    def _smtp_connection(self, record: PlatformSettingsRecord) -> smtplib.SMTP:
        if record.smtp_encryption == "SSL":
            client: smtplib.SMTP = smtplib.SMTP_SSL(record.smtp_host, record.smtp_port, timeout=10)
        else:
            client = smtplib.SMTP(record.smtp_host, record.smtp_port, timeout=10)
        try:
            if record.smtp_encryption == "STARTTLS":
                client.starttls()
            if record.smtp_username:
                client.login(
                    record.smtp_username, self.decrypt_password(record.smtp_password_encrypted)
                )
        except Exception:
            client.close()
            raise
        return client

    def send_test_email(self, context: AuthContext, recipient: str) -> ActionResponse:
        self._authorize(context)
        record = self.repository.get()
        message = EmailMessage()
        message["Subject"] = "Adverse SMTP test successful"
        message["From"] = f"{record.smtp_sender_name} <{record.smtp_sender_email}>"
        message["To"] = recipient
        message.set_content("Your Adverse SMTP configuration is working correctly.")
        message.add_alternative(
            branded_email_html(
                eyebrow="Platform settings",
                title="SMTP test successful",
                description=(
                    "Your Adverse mail configuration is connected and ready to send email."
                ),
                action_label="Open Adverse",
                action_url=settings.allowed_origins[0],
                expiry_minutes=30,
            ),
            subtype="html",
        )
        try:
            with self._smtp_connection(record) as client:
                client.send_message(message)
        except (OSError, smtplib.SMTPException) as error:
            raise AuthenticationError(
                502, "SMTP_CONNECTION_FAILED", "The SMTP server could not send the test email."
            ) from error
        self.repository.audit(context.user_id, "TEST_EMAIL_SENT")
        return ActionResponse(code="TEST_EMAIL_SENT", detail=f"Test email sent to {recipient}.")

    async def upload(
        self, context: AuthContext, asset: str, upload: UploadFile
    ) -> BrandingAssetResponse:
        self._authorize(context)
        if asset not in {"logo", "favicon"}:
            raise AuthenticationError(422, "INVALID_ASSET", "Asset must be logo or favicon.")
        extension = self._mime_extensions.get(upload.content_type or "")
        if extension is None:
            raise AuthenticationError(422, "INVALID_IMAGE", "Use PNG, JPEG, WebP, or ICO.")
        content = await upload.read(2 * 1024 * 1024 + 1)
        if not content or len(content) > 2 * 1024 * 1024:
            raise AuthenticationError(422, "INVALID_IMAGE_SIZE", "Image must be 2 MB or smaller.")
        if not self._image_signatures[extension](content):
            raise AuthenticationError(
                422, "INVALID_IMAGE_CONTENT", "The uploaded file is not a valid image."
            )
        self._upload_root.mkdir(parents=True, exist_ok=True)
        filename = f"{asset}-{uuid4().hex}{extension}"
        path = self._upload_root / filename
        path.write_bytes(content)
        url = f"/storage/platform-branding/{filename}"
        field = "platform_logo_url" if asset == "logo" else "favicon_url"
        action = "LOGO_UPDATED" if asset == "logo" else "FAVICON_UPDATED"
        self.repository.update(context.user_id, {field: url}, action)
        return BrandingAssetResponse(asset=cast(Literal["logo", "favicon"], asset), url=url)

    def is_ready(self) -> bool:
        return self.repository.is_ready()


platform_settings_service = PlatformSettingsService()
