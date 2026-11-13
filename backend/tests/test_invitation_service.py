import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

from pydantic import ValidationError

from app.repositories.invitation_repository import InvitationConflict, InvitationRecord
from app.schemas.authentication import AuthContext
from app.schemas.invitations import InvitationAcceptRequest, InvitationCreate
from app.services.authentication_service import AuthenticationError
from app.services.invitation_service import InvitationService, invitation_token_hash


class InvitationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.company_id = uuid4()
        self.user_id = uuid4()
        now = datetime.now(UTC)
        self.context = AuthContext(
            user_id=self.user_id,
            role="COMPANY_ADMIN",
            company_id=self.company_id,
            user_type="company",
            session_id=uuid4(),
            issued_at=now,
            expires_at=now + timedelta(minutes=30),
        )
        self.record = InvitationRecord(
            id=uuid4(),
            email="invitee@example.com",
            company_name="Tenant A",
            invited_by_name="Company Admin",
            status="PENDING",
            expires_at=now + timedelta(hours=48),
            accepted_at=None,
            created_at=now,
        )
        self.repository = MagicMock()
        self.repository.create.return_value = self.record
        self.service = InvitationService(self.repository)

    @patch("app.services.invitation_service.validate_user_action_access", return_value=True)
    @patch("app.services.invitation_service.email_service.send_invitation")
    def test_create_is_tenant_bound_and_stores_only_hash(
        self, send_email: MagicMock, _: MagicMock
    ) -> None:
        response = self.service.create(self.context, InvitationCreate(email=self.record.email))
        self.assertEqual(response.email, self.record.email)
        company_id, actor_id, email, token_hash, _ = self.repository.create.call_args.args
        self.assertEqual(company_id, self.company_id)
        self.assertEqual(actor_id, self.user_id)
        self.assertEqual(email, self.record.email)
        self.assertEqual(len(token_hash), 64)
        self.assertNotIn(token_hash, send_email.call_args.kwargs["invitation_url"])
        send_email.assert_called_once()

    @patch("app.services.invitation_service.validate_user_action_access", return_value=True)
    def test_duplicate_pending_invitation_returns_conflict(self, _: MagicMock) -> None:
        self.repository.create.side_effect = InvitationConflict("INVITATION_EXISTS")
        with self.assertRaises(AuthenticationError) as raised:
            self.service.create(self.context, InvitationCreate(email=self.record.email))
        self.assertEqual(raised.exception.status_code, 409)

    def test_non_admin_cannot_manage_invitations(self) -> None:
        context = self.context.model_copy(update={"role": "COMPANY_EMPLOYEE"})
        with self.assertRaises(AuthenticationError) as raised:
            self.service.list(context)
        self.assertEqual(raised.exception.status_code, 403)

    @patch("app.services.invitation_service.validate_user_action_access", return_value=False)
    def test_missing_permission_is_forbidden(self, _: MagicMock) -> None:
        with self.assertRaises(AuthenticationError) as raised:
            self.service.list(self.context)
        self.assertEqual(raised.exception.status_code, 403)

    def test_invalid_and_expired_tokens_are_rejected(self) -> None:
        self.repository.find_by_hash.return_value = None
        with self.assertRaises(AuthenticationError) as invalid:
            self.service.validate("x" * 40)
        self.assertEqual(invalid.exception.status_code, 400)

        expired = InvitationRecord(**{**self.record.__dict__, "status": "EXPIRED"})
        self.repository.find_by_hash.return_value = (expired, self.company_id, self.user_id)
        with self.assertRaises(AuthenticationError) as expired_error:
            self.service.validate("y" * 40)
        self.assertEqual(expired_error.exception.status_code, 410)

    @patch("app.services.invitation_service.hash_password", return_value="secure-hash")
    def test_accept_creates_user_from_invitation_tenant(self, hash_password: MagicMock) -> None:
        self.repository.find_by_hash.return_value = (self.record, self.company_id, self.user_id)
        self.repository.accept.return_value = (self.record.email, self.record.company_name)
        request = InvitationAcceptRequest(
            token="secure-token-that-is-long-enough-for-validation",
            name="Invited Employee",
            password="StrongPassword@123",
            confirm_password="StrongPassword@123",
        )
        response = self.service.accept(request)
        expected_hash = invitation_token_hash(request.token)
        self.repository.accept.assert_called_once_with(
            expected_hash, "Invited Employee", "secure-hash"
        )
        hash_password.assert_called_once_with("StrongPassword@123")
        self.assertEqual(response.email, self.record.email)

    def test_accept_schema_rejects_weak_or_mismatched_password(self) -> None:
        with self.assertRaises(ValidationError):
            InvitationAcceptRequest(
                token="secure-token-that-is-long-enough-for-validation",
                name="Invited Employee",
                password="weak-password",
                confirm_password="different-password",
            )


if __name__ == "__main__":
    unittest.main()
