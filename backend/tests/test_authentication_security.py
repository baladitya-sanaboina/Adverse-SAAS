import base64
import hashlib
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.repositories.authentication_repository import (
    AuthenticationUserRecord,
    LoginProtectionRecord,
)
from app.schemas.authentication import LoginRequest
from app.services.authentication_service import AuthenticationError, AuthenticationService
from app.services.password_service import hash_password, needs_rehash, verify_password


class FakeSecurityRepository:
    def __init__(self) -> None:
        self.user = AuthenticationUserRecord(
            uuid4(),
            "Security User",
            "security@loopless.in",
            hash_password("CorrectPass!123"),
            "ACTIVE",
            "PLATFORM_OWNER",
            "ACTIVE",
            None,
            None,
            None,
            None,
            0,
            None,
        )
        self.failed_attempts = 0
        self.locked_until = None
        self.events: list[str] = []
        self.protection_cleared = False

    def recent_failed_logins(self, email, ip_address, since):
        return self.failed_attempts

    def find_user_by_email(self, email):
        if email != self.user.email:
            return None
        return replace(
            self.user,
            failed_login_attempts=self.failed_attempts,
            locked_until=self.locked_until,
        )

    def record_failed_login(self, user_id, maximum_attempts, lock_duration):
        self.failed_attempts += 1
        if self.failed_attempts >= maximum_attempts:
            self.locked_until = lock_duration
        return LoginProtectionRecord(self.failed_attempts, self.locked_until)

    def clear_login_protection(self, user_id):
        self.failed_attempts = 0
        self.locked_until = None
        self.protection_cleared = True

    def log_event(self, event_type, **kwargs):
        self.events.append(event_type)

    def create_session(self, user_id, company_id, refresh_hash, expires_at, device_info):
        return uuid4()

    def set_refresh_hash(self, session_id, refresh_hash):
        return None

    def update_password_hash(self, user_id, password_hash):
        self.user = replace(self.user, password_hash=password_hash)


class AuthenticationSecurityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = FakeSecurityRepository()
        self.service = AuthenticationService(self.repository)

    def test_five_failed_attempts_lock_account_and_log_event(self):
        request = LoginRequest(email=self.repository.user.email, password="WrongPass!123")
        for _ in range(4):
            with self.assertRaisesRegex(AuthenticationError, "incorrect"):
                self.service.login(request, "test", "127.0.0.1")
        with self.assertRaises(AuthenticationError) as raised:
            self.service.login(request, "test", "127.0.0.1")
        self.assertEqual(raised.exception.status_code, 429)
        self.assertEqual(raised.exception.code, "ACCOUNT_LOCKED")
        self.assertIn("ACCOUNT_LOCKED", self.repository.events)

    def test_rate_limit_blocks_repeated_unknown_account_attempts(self):
        self.repository.failed_attempts = 5
        with self.assertRaises(AuthenticationError) as raised:
            self.service.login(
                LoginRequest(email="unknown@loopless.in", password="WrongPass!123"),
                "test",
                "127.0.0.1",
            )
        self.assertEqual(raised.exception.code, "LOGIN_RATE_LIMITED")

    def test_successful_login_clears_failed_attempts(self):
        self.repository.failed_attempts = 2
        response = self.service.login(
            LoginRequest(email=self.repository.user.email, password="CorrectPass!123"),
            "test",
            "127.0.0.1",
        )
        self.assertEqual(response.user.email, self.repository.user.email)
        self.assertTrue(self.repository.protection_cleared)
        self.assertIn("LOGIN_SUCCESS", self.repository.events)

    def test_expired_account_lock_is_cleared_automatically(self):
        self.repository.failed_attempts = 5
        self.repository.locked_until = datetime.now(UTC) - timedelta(minutes=1)
        response = self.service.login(
            LoginRequest(email=self.repository.user.email, password="CorrectPass!123"),
            "test",
            "127.0.0.1",
        )
        self.assertEqual(response.user.email, self.repository.user.email)
        self.assertTrue(self.repository.protection_cleared)

    def test_old_weaker_hash_is_upgraded_on_sign_in(self):
        salt = b"0123456789abcdef"
        key = hashlib.scrypt(b"CorrectPass!123", salt=salt, n=2**14, r=8, p=1)
        old = (
            f"scrypt$16384$8$1${base64.urlsafe_b64encode(salt).decode()}"
            f"${base64.urlsafe_b64encode(key).decode()}"
        )
        self.repository.user = replace(self.repository.user, password_hash=old)
        self.assertTrue(needs_rehash(old))
        self.service.login(
            LoginRequest(email=self.repository.user.email, password="CorrectPass!123"),
            "test",
            "127.0.0.1",
        )
        upgraded = self.repository.user.password_hash
        self.assertNotEqual(upgraded, old)
        self.assertFalse(needs_rehash(upgraded))
        self.assertTrue(verify_password("CorrectPass!123", upgraded))


if __name__ == "__main__":
    unittest.main()
