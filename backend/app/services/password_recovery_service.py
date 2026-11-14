import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID

from app.core.settings import settings
from app.repositories.password_recovery_repository import (
    PasswordRecoveryRepository,
    PasswordResetRecord,
    RecoveryUserRecord,
)
from app.schemas.authentication import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
)
from app.services.authentication_service import AuthenticationError
from app.services.email_service import PasswordResetEmailSender, email_service
from app.services.password_service import hash_password


def reset_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def reset_otp_hash(user_id: UUID, otp: str) -> str:
    return reset_token_hash(f"{user_id}:{otp}")


class PasswordRecoveryRepositoryProtocol(Protocol):
    def find_user_by_email(self, email: str) -> RecoveryUserRecord | None: ...

    def create_reset_token(self, user_id: UUID, token_hash: str, expires_at: datetime) -> None: ...

    def find_reset_token(self, token_hash: str) -> PasswordResetRecord | None: ...

    def consume_reset_token(self, token_id: UUID, user_id: UUID, password_hash: str) -> bool: ...

    def foundation_is_ready(self) -> bool: ...


class PasswordRecoveryService:
    def __init__(
        self,
        repository: PasswordRecoveryRepositoryProtocol | None = None,
        email_sender: PasswordResetEmailSender | None = None,
    ):
        self.repository = repository or PasswordRecoveryRepository()
        self.email_sender = email_sender or email_service

    def forgot_password(self, request: ForgotPasswordRequest) -> ForgotPasswordResponse:
        user = self.repository.find_user_by_email(str(request.email).lower())
        if user is None or user.status != "ACTIVE":
            return ForgotPasswordResponse()

        otp = f"{secrets.randbelow(900000) + 100000:06d}"
        expires_at = datetime.now(UTC) + timedelta(minutes=settings.password_reset_expiry_minutes)
        self.repository.create_reset_token(user.id, reset_otp_hash(user.id, otp), expires_at)
        self.email_sender.send_password_reset(user.email, otp)
        return ForgotPasswordResponse()

    def reset_password(self, request: ResetPasswordRequest) -> ResetPasswordResponse:
        if request.token:
            record = self.repository.find_reset_token(reset_token_hash(request.token))
        else:
            user = (
                self.repository.find_user_by_email(str(request.email).lower())
                if request.email
                else None
            )
            if user is None:
                record = None
            else:
                record = self.repository.find_reset_token(
                    reset_otp_hash(user.id, request.otp or "")
                )
        if record is None:
            raise AuthenticationError(
                400, "INVALID_RESET_TOKEN", "Password reset code or link is invalid."
            )
        if record.used_at is not None:
            raise AuthenticationError(
                400, "RESET_TOKEN_USED", "Password reset code or link has already been used."
            )
        expires_at = record.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at <= datetime.now(UTC):
            raise AuthenticationError(
                400, "RESET_TOKEN_EXPIRED", "Password reset code or link has expired."
            )
        if record.user_status != "ACTIVE":
            raise AuthenticationError(403, "USER_INACTIVE", "User account is not active.")
        consumed = self.repository.consume_reset_token(
            record.id,
            record.user_id,
            hash_password(request.new_password.get_secret_value()),
        )
        if not consumed:
            raise AuthenticationError(
                400, "INVALID_RESET_TOKEN", "Password reset code or link is invalid or expired."
            )
        return ResetPasswordResponse()

    def is_ready(self) -> bool:
        return self.repository.foundation_is_ready()


password_recovery_service = PasswordRecoveryService()
