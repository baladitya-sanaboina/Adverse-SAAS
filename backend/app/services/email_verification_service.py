import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID

from app.core.settings import settings
from app.repositories.email_verification_repository import (
    EmailVerificationRepository,
    VerificationTokenRecord,
    VerificationUserRecord,
)
from app.schemas.authentication import (
    VerificationEmailResponse,
    VerifyEmailResponse,
)
from app.services.authentication_service import AuthenticationError
from app.services.email_service import VerificationEmailSender, email_service


def verification_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verification_otp_hash(user_id: UUID, otp: str) -> str:
    return verification_token_hash(f"{user_id}:{otp}")


class EmailVerificationRepositoryProtocol(Protocol):
    def find_user_by_email(self, email: str) -> VerificationUserRecord | None: ...
    def create_token(self, user_id: UUID, token_hash: str, expires_at: datetime) -> None: ...
    def seconds_since_latest(self, user_id: UUID) -> float | None: ...
    def find_token(self, token_hash: str) -> VerificationTokenRecord | None: ...
    def activate_user(self, token_id: UUID, user_id: UUID) -> bool: ...
    def foundation_is_ready(self) -> bool: ...


class EmailVerificationService:
    def __init__(
        self,
        repository: EmailVerificationRepositoryProtocol | None = None,
        email_sender: VerificationEmailSender | None = None,
    ):
        self.repository = repository or EmailVerificationRepository()
        self.email_sender = email_sender or email_service

    def send(self, email: str, *, enforce_rate_limit: bool = True) -> VerificationEmailResponse:
        user = self.repository.find_user_by_email(email.lower())
        if user is None:
            return VerificationEmailResponse()
        if user.status == "ACTIVE":
            raise AuthenticationError(
                409, "EMAIL_ALREADY_VERIFIED", "Email address is already verified."
            )
        if user.status != "PENDING_VERIFICATION":
            raise AuthenticationError(403, "USER_INACTIVE", "User account cannot be verified.")
        elapsed = self.repository.seconds_since_latest(user.id)
        if (
            enforce_rate_limit
            and elapsed is not None
            and elapsed < settings.email_verification_resend_seconds
        ):
            raise AuthenticationError(
                429,
                "VERIFICATION_RATE_LIMITED",
                "Please wait before requesting another verification email.",
            )
        otp = f"{secrets.randbelow(900000) + 100000:06d}"
        expires_at = datetime.now(UTC) + timedelta(
            minutes=settings.email_verification_expiry_minutes
        )
        self.repository.create_token(user.id, verification_otp_hash(user.id, otp), expires_at)
        self.email_sender.send_verification(user.email, otp)
        return VerificationEmailResponse()

    def start_for_created_user(self, email: str) -> None:
        self.send(email, enforce_rate_limit=False)

    def verify(self, token: str) -> VerifyEmailResponse:
        record = self.repository.find_token(verification_token_hash(token))
        return self._consume_record(record)

    def verify_otp(self, email: str, otp: str) -> VerifyEmailResponse:
        user = self.repository.find_user_by_email(email.lower())
        if user is None:
            raise AuthenticationError(
                400, "INVALID_VERIFICATION_TOKEN", "Verification code is invalid."
            )
        record = self.repository.find_token(verification_otp_hash(user.id, otp))
        return self._consume_record(record)

    def _consume_record(self, record: VerificationTokenRecord | None) -> VerifyEmailResponse:
        if record is None:
            raise AuthenticationError(
                400, "INVALID_VERIFICATION_TOKEN", "Verification code or link is invalid."
            )
        expires_at = (
            record.expires_at if record.expires_at.tzinfo else record.expires_at.replace(tzinfo=UTC)
        )
        if expires_at <= datetime.now(UTC):
            raise AuthenticationError(
                400, "VERIFICATION_TOKEN_EXPIRED", "Verification code or link has expired."
            )
        if record.user_status == "ACTIVE":
            raise AuthenticationError(
                409, "EMAIL_ALREADY_VERIFIED", "Email address is already verified."
            )
        if record.user_status != "PENDING_VERIFICATION":
            raise AuthenticationError(403, "USER_INACTIVE", "User account cannot be verified.")
        if not self.repository.activate_user(record.id, record.user_id):
            raise AuthenticationError(
                400, "INVALID_VERIFICATION_TOKEN", "Verification code or link is invalid or expired."
            )
        return VerifyEmailResponse()

    def is_ready(self) -> bool:
        return self.repository.foundation_is_ready()


email_verification_service = EmailVerificationService()
