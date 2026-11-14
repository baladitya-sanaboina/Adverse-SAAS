import unittest
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.repositories.email_verification_repository import (
    VerificationTokenRecord,
    VerificationUserRecord,
)
from app.services.authentication_service import AuthenticationError
from app.services.email_verification_service import (
    MAX_CODE_ATTEMPTS,
    EmailVerificationService,
    verification_otp_hash,
)


class FakeRepository:
    def __init__(self):
        self.user = VerificationUserRecord(
            uuid4(), "pending@example.com", "PENDING_VERIFICATION", "COMPANY_EMPLOYEE"
        )
        self.token_hash = ""
        self.token = None
        self.elapsed = None
        self.attempts = 0

    def find_user_by_email(self, email):
        return self.user if email == self.user.email else None

    def create_token(self, user_id, token_hash, expires_at):
        self.token_hash = token_hash
        self.attempts = 0
        self.token = VerificationTokenRecord(uuid4(), user_id, expires_at, self.user.status)

    def seconds_since_latest(self, user_id):
        return self.elapsed

    def use_attempt(self, user_id):
        if self.token is None:
            return None
        self.attempts += 1
        return self.attempts

    def find_token(self, token_hash):
        return self.token if token_hash == self.token_hash else None

    def activate_user(self, token_id, user_id):
        if self.token is None or self.token.id != token_id:
            return False
        self.token = None
        self.user = VerificationUserRecord(self.user.id, self.user.email, "ACTIVE", self.user.role)
        return True

    def foundation_is_ready(self):
        return True


class FakeEmailSender:
    def __init__(self):
        self.email = ""
        self.code = ""

    def send_verification(self, email, verification_code):
        self.email = email
        self.code = verification_code


class EmailVerificationTests(unittest.TestCase):
    def setUp(self):
        self.repository = FakeRepository()
        self.sender = FakeEmailSender()
        self.service = EmailVerificationService(self.repository, self.sender)

    def issue_code(self):
        self.service.send("pending@example.com")
        return self.sender.code

    def test_send_stores_only_hash_and_delivers_code(self):
        code = self.issue_code()
        self.assertEqual(self.sender.email, "pending@example.com")
        self.assertEqual(
            self.repository.token_hash, verification_otp_hash(self.repository.user.id, code)
        )
        self.assertNotEqual(self.repository.token_hash, code)
        self.assertRegex(code, r"^\d{6}$")

    def test_valid_code_activates_account_and_prevents_replay(self):
        code = self.issue_code()
        response = self.service.verify_otp("pending@example.com", code)
        self.assertIn("verified", response.message.lower())
        self.assertEqual(self.repository.user.status, "ACTIVE")
        with self.assertRaises(AuthenticationError) as context:
            self.service.verify_otp("pending@example.com", code)
        self.assertEqual(context.exception.code, "INVALID_VERIFICATION_TOKEN")

    def test_invalid_and_expired_codes_are_rejected(self):
        self.issue_code()
        with self.assertRaises(AuthenticationError) as invalid:
            self.service.verify_otp("pending@example.com", "123456")
        self.assertEqual(invalid.exception.code, "INVALID_VERIFICATION_TOKEN")
        self.repository.token = VerificationTokenRecord(
            self.repository.token.id,
            self.repository.user.id,
            datetime.now(UTC) - timedelta(seconds=1),
            "PENDING_VERIFICATION",
        )
        code = self.sender.code
        with self.assertRaises(AuthenticationError) as expired:
            self.service.verify_otp("pending@example.com", code)
        self.assertEqual(expired.exception.code, "VERIFICATION_TOKEN_EXPIRED")

    def test_resend_is_rate_limited_and_active_account_is_rejected(self):
        self.repository.elapsed = 1
        with self.assertRaises(AuthenticationError) as limited:
            self.service.send("pending@example.com")
        self.assertEqual(limited.exception.status_code, 429)
        self.repository.user = VerificationUserRecord(
            self.repository.user.id, self.repository.user.email, "ACTIVE", self.repository.user.role
        )
        self.repository.elapsed = None
        with self.assertRaises(AuthenticationError) as verified:
            self.service.send("pending@example.com")
        self.assertEqual(verified.exception.code, "EMAIL_ALREADY_VERIFIED")

    def test_code_is_locked_after_too_many_wrong_guesses(self):
        code = self.issue_code()
        wrong = "100000" if code != "100000" else "100001"
        for _ in range(MAX_CODE_ATTEMPTS):
            with self.assertRaisesRegex(AuthenticationError, "invalid"):
                self.service.verify_otp("pending@example.com", wrong)
        with self.assertRaises(AuthenticationError) as caught:
            self.service.verify_otp("pending@example.com", code)
        self.assertEqual(caught.exception.code, "VERIFICATION_ATTEMPTS_EXCEEDED")
        self.assertEqual(self.repository.user.status, "PENDING_VERIFICATION")
        with self.assertRaises(AuthenticationError) as again:
            self.service.verify_otp("pending@example.com", code)
        self.assertEqual(again.exception.code, "VERIFICATION_ATTEMPTS_EXCEEDED")


if __name__ == "__main__":
    unittest.main()
