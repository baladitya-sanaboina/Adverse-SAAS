import unittest
from uuid import uuid4

from app.services.jwt_service import (
    TokenValidationError,
    create_access_token,
    create_refresh_token,
    decode_token,
)


class JwtFoundationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.user_id = uuid4()
        self.company_id = uuid4()
        self.session_id = uuid4()

    def test_access_token_contains_required_context(self) -> None:
        token = create_access_token(self.user_id, "COMPANY_ADMIN", self.company_id, self.session_id)
        claims = decode_token(token, "access")
        self.assertEqual(claims.user_id, self.user_id)
        self.assertEqual(claims.company_id, self.company_id)
        self.assertEqual(claims.role, "COMPANY_ADMIN")
        self.assertEqual(claims.user_type, "company")
        self.assertEqual(claims.session_id, self.session_id)
        self.assertGreater(claims.expires_at, claims.issued_at)

    def test_refresh_token_has_refresh_type(self) -> None:
        token = create_refresh_token(self.user_id, "PLATFORM_OWNER", None, self.session_id)
        claims = decode_token(token, "refresh")
        self.assertEqual(claims.token_type, "refresh")
        self.assertEqual(claims.user_type, "platform")

    def test_refresh_tokens_are_unique_for_rotation(self) -> None:
        first = create_refresh_token(self.user_id, "PLATFORM_OWNER", None, self.session_id)
        second = create_refresh_token(self.user_id, "PLATFORM_OWNER", None, self.session_id)
        self.assertNotEqual(first, second)

    def test_token_type_cannot_be_substituted(self) -> None:
        token = create_refresh_token(self.user_id, "PLATFORM_OWNER", None, self.session_id)
        with self.assertRaises(TokenValidationError):
            decode_token(token, "access")

    def test_malformed_token_is_rejected(self) -> None:
        with self.assertRaises(TokenValidationError):
            decode_token("not-a-jwt", "access")


if __name__ == "__main__":
    unittest.main()
