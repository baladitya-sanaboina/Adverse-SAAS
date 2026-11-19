import unittest
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from pydantic import ValidationError

from app.repositories.password_recovery_repository import (
    PasswordResetRecord,
    RecoveryUserRecord,
)
from app.schemas.authentication import ForgotPasswordRequest, ResetPasswordRequest
from app.services.authentication_service import AuthenticationError
from app.services.password_recovery_service import (
    MAX_CODE_ATTEMPTS,
    RESEND_COOLDOWN_SECONDS,
    PasswordRecoveryService,
    reset_otp_hash,
)
from app.services.password_service import verify_password


class FakeRecoveryRepository:
    def __init__(self):
        self.user = RecoveryUserRecord(uuid4(), "user@example.com", "ACTIVE", "COMPANY_EMPLOYEE")
        self.token: PasswordResetRecord | None = None
        self.token_hash = ""
        self.password_hash = ""
        self.sessions_revoked = False
        self.attempts = 0
        self.elapsed: float | None = None

    def find_user_by_email(self, email: str):
        return self.user if email == self.user.email else None

    def create_reset_token(self, user_id, token_hash, expires_at):
        self.token_hash = token_hash
        self.attempts = 0
        self.token = PasswordResetRecord(uuid4(), user_id, expires_at, None, "ACTIVE")

    def seconds_since_latest(self, user_id):
        return self.elapsed

    def use_attempt(self, user_id):
        if self.token is None or self.token.used_at is not None:
            return None
        self.attempts += 1
        return self.attempts

    def find_reset_token(self, token_hash: str):
        return self.token if token_hash == self.token_hash else None

    def consume_reset_token(self, token_id, user_id, password_hash):
        if self.token is None or self.token.used_at is not None:
            return False
        self.password_hash = password_hash
        self.sessions_revoked = True
        self.token = PasswordResetRecord(
            self.token.id,
            self.token.user_id,
            self.token.expires_at,
            datetime.now(UTC),
            self.token.user_status,
        )
        return True

    def foundation_is_ready(self):
        return True


class FakeEmailSender:
    def __init__(self):
        self.email = ""
        self.reset_code = ""

    def send_password_reset(self, email: str, reset_code: str, login_email: str | None = None):
        self.email = email
        self.reset_code = reset_code
        self.login_email = login_email


class PasswordRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.repository = FakeRecoveryRepository()
        self.email = FakeEmailSender()
        self.service = PasswordRecoveryService(self.repository, self.email)

    def request_code(self) -> str:
        self.service.forgot_password(ForgotPasswordRequest(email="user@example.com"))
        return self.email.reset_code

    def test_forgot_password_stores_only_hash_and_triggers_email(self):
        code = self.request_code()
        self.assertEqual(self.email.email, "user@example.com")
        self.assertEqual(self.repository.token_hash, reset_otp_hash(self.repository.user.id, code))
        self.assertNotEqual(self.repository.token_hash, code)
        self.assertRegex(code, r"^\d{6}$")

    def test_code_goes_to_their_gmail_not_the_internal_login(self):
        """Owner request 2026-11-19: forgot password reaches their own Gmail."""
        self.repository.user = RecoveryUserRecord(
            self.repository.user.id,
            "ravi@adverseindia.com",
            "ACTIVE",
            "COMPANY_EMPLOYEE",
            "ravi@gmail.com",
        )
        self.service.forgot_password(ForgotPasswordRequest(email="ravi@adverseindia.com"))
        self.assertEqual(self.email.email, "ravi@gmail.com")
        self.assertEqual(self.email.login_email, "ravi@adverseindia.com")

    def test_internal_login_without_gmail_gets_no_mail(self):
        self.repository.user = RecoveryUserRecord(
            self.repository.user.id, "ravi@adverseindia.com", "ACTIVE", "COMPANY_EMPLOYEE", None
        )
        response = self.service.forgot_password(
            ForgotPasswordRequest(email="ravi@adverseindia.com")
        )
        self.assertIn("eligible", response.message)  # same answer, nothing sent
        self.assertEqual(self.email.reset_code, "")

    def test_unknown_email_gets_same_generic_response(self):
        response = self.service.forgot_password(ForgotPasswordRequest(email="unknown@example.com"))
        self.assertIn("eligible", response.message)
        self.assertEqual(self.email.reset_code, "")

    def test_valid_code_updates_hash_revokes_sessions_and_becomes_single_use(self):
        code = self.request_code()
        request = ResetPasswordRequest(
            email="user@example.com",
            otp=code,
            new_password="NewStrongPass!123",
            confirm_password="NewStrongPass!123",
        )
        self.service.reset_password(request)
        self.assertTrue(verify_password("NewStrongPass!123", self.repository.password_hash))
        self.assertTrue(self.repository.sessions_revoked)
        with self.assertRaisesRegex(AuthenticationError, "already been used"):
            self.service.reset_password(request)

    def test_expired_and_invalid_codes_are_rejected(self):
        code = self.request_code()
        assert self.repository.token is not None
        self.repository.token = PasswordResetRecord(
            self.repository.token.id,
            self.repository.token.user_id,
            datetime.now(UTC) - timedelta(seconds=1),
            None,
            "ACTIVE",
        )
        with self.assertRaisesRegex(AuthenticationError, "expired"):
            self.service.reset_password(
                ResetPasswordRequest(
                    email="user@example.com",
                    otp=code,
                    new_password="NewStrongPass!123",
                    confirm_password="NewStrongPass!123",
                )
            )
        with self.assertRaisesRegex(AuthenticationError, "invalid"):
            self.service.reset_password(
                ResetPasswordRequest(
                    email="user@example.com",
                    otp="123456",
                    new_password="NewStrongPass!123",
                    confirm_password="NewStrongPass!123",
                )
            )

    def reset_with(self, code: str) -> None:
        self.service.reset_password(
            ResetPasswordRequest(
                email="user@example.com",
                otp=code,
                new_password="NewStrongPass!123",
                confirm_password="NewStrongPass!123",
            )
        )

    def test_code_is_locked_after_too_many_wrong_guesses(self):
        code = self.request_code()
        wrong = "100000" if code != "100000" else "100001"
        for _ in range(MAX_CODE_ATTEMPTS):
            with self.assertRaisesRegex(AuthenticationError, "invalid"):
                self.reset_with(wrong)
        with self.assertRaises(AuthenticationError) as caught:
            self.reset_with(code)
        self.assertEqual(caught.exception.code, "RESET_ATTEMPTS_EXCEEDED")
        self.assertEqual(self.repository.password_hash, "")
        # The used-up code stays blocked, and a new one still waits for the resend gap.
        self.repository.elapsed = 5
        self.email.reset_code = ""
        self.service.forgot_password(ForgotPasswordRequest(email="user@example.com"))
        self.assertEqual(self.email.reset_code, "")
        with self.assertRaises(AuthenticationError) as again:
            self.reset_with(code)
        self.assertEqual(again.exception.code, "RESET_ATTEMPTS_EXCEEDED")
        self.assertEqual(self.repository.password_hash, "")

    def test_right_code_within_the_limit_still_works(self):
        code = self.request_code()
        wrong = "100000" if code != "100000" else "100001"
        for _ in range(MAX_CODE_ATTEMPTS - 1):
            with self.assertRaisesRegex(AuthenticationError, "invalid"):
                self.reset_with(wrong)
        self.reset_with(code)
        self.assertTrue(verify_password("NewStrongPass!123", self.repository.password_hash))

    def test_new_code_is_not_sent_again_straight_away(self):
        first = self.request_code()
        self.repository.elapsed = 5
        self.email.reset_code = ""
        self.service.forgot_password(ForgotPasswordRequest(email="user@example.com"))
        self.assertEqual(self.email.reset_code, "")
        self.assertEqual(self.repository.token_hash, reset_otp_hash(self.repository.user.id, first))
        self.repository.elapsed = RESEND_COOLDOWN_SECONDS + 1
        self.assertRegex(self.request_code(), r"^\d{6}$")

    def test_token_fallback_is_still_supported(self):
        request = ResetPasswordRequest(
            token="legacy-token-value-that-is-long-enough-123456",
            new_password="NewStrongPass!123",
            confirm_password="NewStrongPass!123",
        )
        self.assertEqual(request.token, "legacy-token-value-that-is-long-enough-123456")

    def test_weak_or_mismatched_password_is_rejected(self):
        with self.assertRaises(ValidationError):
            ResetPasswordRequest(
                email="user@example.com",
                otp="123456",
                new_password="weakpassword",
                confirm_password="weakpassword",
            )
        with self.assertRaises(ValidationError):
            ResetPasswordRequest(
                email="user@example.com",
                otp="123456",
                new_password="NewStrongPass!123",
                confirm_password="DifferentPass!123",
            )


if __name__ == "__main__":
    unittest.main()
