import unittest
from datetime import UTC, datetime
from unittest.mock import patch
from uuid import uuid4

from fastapi import HTTPException

from app.middleware.permissions import PermissionRequirement
from app.schemas.authentication import AuthContext


class PermissionEnforcementTests(unittest.TestCase):
    def context(self) -> AuthContext:
        now = datetime.now(UTC)
        return AuthContext(
            user_id=uuid4(),
            role="DEVELOPER",
            company_id=None,
            user_type="platform",
            session_id=uuid4(),
            issued_at=now,
            expires_at=now,
        )

    @patch("app.middleware.permissions.validate_user_action_access", return_value=True)
    def test_assigned_permission_allows_request(self, permission_check) -> None:
        PermissionRequirement("COMPANIES", "VIEW")(self.context())
        permission_check.assert_called_once()

    @patch("app.middleware.permissions.validate_user_action_access", return_value=False)
    def test_missing_permission_returns_forbidden(self, permission_check) -> None:
        with self.assertRaises(HTTPException) as raised:
            PermissionRequirement("COMPANIES", "CREATE")(self.context())
        self.assertEqual(raised.exception.status_code, 403)
        permission_check.assert_called_once()


if __name__ == "__main__":
    unittest.main()
