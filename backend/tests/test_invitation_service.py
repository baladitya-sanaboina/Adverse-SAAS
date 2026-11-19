import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

from pydantic import ValidationError

from app.core.settings import settings
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
            email="invitee@adverseindia.com",
            notification_email="personal@gmail.com",
            company_name="Tenant A",
            invited_by_name="Company Admin",
            role_code="COMPANY_EMPLOYEE",
            status="PENDING",
            expires_at=now + timedelta(hours=48),
            accepted_at=None,
            created_at=now,
        )
        self.repository = MagicMock()
        self.repository.create.return_value = self.record
        self.repository.gmail_in_use.return_value = None
        self.repository.department_ok.return_value = True
        self.service = InvitationService(self.repository)

    @patch("app.services.invitation_service.validate_user_action_access", return_value=True)
    @patch("app.services.invitation_service.email_service.send_invitation")
    def test_create_is_tenant_bound_and_stores_only_hash(
        self, send_email: MagicMock, _: MagicMock
    ) -> None:
        self.repository.create.return_value = InvitationRecord(
            **{**self.record.__dict__, "role_code": "COMPANY_MANAGER"}
        )
        response = self.service.create(
            self.context,
            InvitationCreate(
                email=self.record.email,
                notification_email=self.record.notification_email,
                name="Invited Employee",
                phone_number="+91 98765 43210",
                role_code="COMPANY_MANAGER",
            ),
        )
        self.assertEqual(response.email, self.record.email)
        self.assertEqual(response.role_code, "COMPANY_MANAGER")
        (
            company_id,
            actor_id,
            email,
            notification_email,
            token_hash,
            _,
            role_code,
            invited_name,
            phone_number,
            password_hash,
            client_id,
        ) = self.repository.create.call_args.args
        self.assertEqual(company_id, self.company_id)
        self.assertEqual(actor_id, self.user_id)
        self.assertEqual(email, self.record.email)
        self.assertEqual(notification_email, self.record.notification_email)
        self.assertEqual(role_code, "COMPANY_MANAGER")
        self.assertEqual(invited_name, "Invited Employee")
        self.assertEqual(phone_number, "+91 98765 43210")
        self.assertTrue(password_hash)
        self.assertIsNone(client_id)
        self.assertEqual(len(token_hash), 64)
        expected_origin = settings.role_origin("COMPANY_MANAGER", "invitation")
        self.assertTrue(
            send_email.call_args.kwargs["invitation_url"].startswith(
                f"{expected_origin}/invitations/accept?token="
            )
        )
        self.assertEqual(send_email.call_args.kwargs["login_email"], self.record.email)
        self.assertNotIn(token_hash, send_email.call_args.kwargs["invitation_url"])
        send_email.assert_called_once()

    @patch("app.services.invitation_service.validate_user_action_access", return_value=True)
    @patch("app.services.invitation_service.email_service.send_invitation")
    def test_resend_keeps_role_specific_acceptance_domain(
        self, send_email: MagicMock, _: MagicMock
    ) -> None:
        invitation_id = uuid4()
        self.repository.resend.return_value = InvitationRecord(
            **{**self.record.__dict__, "id": invitation_id, "role_code": "COMPANY_CLIENT"}
        )

        response = self.service.resend(self.context, invitation_id)

        self.assertEqual(response.message, "Invitation resent successfully.")
        expected_origin = settings.role_origin("COMPANY_CLIENT", "invitation")
        self.assertTrue(
            send_email.call_args.kwargs["invitation_url"].startswith(
                f"{expected_origin}/invitations/accept?token="
            )
        )

    @patch("app.services.invitation_service.validate_user_action_access", return_value=True)
    def test_duplicate_pending_invitation_returns_conflict(self, _: MagicMock) -> None:
        self.repository.create.side_effect = InvitationConflict("INVITATION_EXISTS")
        with self.assertRaises(AuthenticationError) as raised:
            self.service.create(
                self.context,
                InvitationCreate(
                    email=self.record.email,
                    notification_email=self.record.notification_email,
                    name="Test",
                    phone_number="+91 98765 43210",
                ),
            )
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
        self.repository.find_by_hash.return_value = (expired, self.company_id, self.user_id, None)
        with self.assertRaises(AuthenticationError) as expired_error:
            self.service.validate("y" * 40)
        self.assertEqual(expired_error.exception.status_code, 410)

    @patch("app.services.invitation_service.hash_password", return_value="secure-hash")
    @patch("app.services.invitation_service.email_service.send_account_ready")
    def test_accept_creates_user_from_invitation_tenant(
        self, send_account_ready: MagicMock, hash_password: MagicMock
    ) -> None:
        self.repository.find_by_hash.return_value = (
            self.record,
            self.company_id,
            self.user_id,
            None,
        )
        self.repository.accept.return_value = (
            self.record.email,
            self.record.notification_email,
            self.record.company_name,
            self.record.role_code,
        )
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
        send_account_ready.assert_called_once_with(
            self.record.notification_email,
            company_name=self.record.company_name,
            login_email=self.record.email,
            login_url=settings.login_url(self.record.role_code),
        )
        self.assertEqual(response.email, self.record.email)
        self.assertEqual(response.role_code, self.record.role_code)
        self.assertIn("/login", response.login_url)

    @patch("app.services.invitation_service.validate_user_action_access", return_value=True)
    @patch("app.services.invitation_service.email_service.send_invitation")
    def test_create_uses_notification_email_when_provided(
        self, send_email: MagicMock, _: MagicMock
    ) -> None:
        response = self.service.create(
            self.context,
            InvitationCreate(
                email="employee@adverseindia.com",
                notification_email="person@gmail.com",
                name="Invited Employee",
                phone_number="+91 98765 43210",
                role_code="COMPANY_EMPLOYEE",
            ),
        )
        self.assertEqual(response.email, self.record.email)
        self.assertEqual(self.repository.create.call_args.args[3], "person@gmail.com")
        self.assertEqual(send_email.call_args.args[0], self.record.notification_email)
        self.assertEqual(send_email.call_args.kwargs["login_email"], self.record.email)

    @patch("app.services.invitation_service.validate_user_action_access", return_value=True)
    @patch("app.services.invitation_service.email_service.send_invitation")
    def test_login_is_internal_and_gmail_is_outside(
        self, send_email: MagicMock, _: MagicMock
    ) -> None:
        """Owner request 2026-11-19: name@adverseindia.com logins; the link goes to their Gmail."""

        def invite(**changes: object) -> str:
            base: dict[str, object] = {
                "email": "ravi.kumar@adverseindia.com",
                "notification_email": "ravi@gmail.com",
                "name": "Ravi Kumar",
                "phone_number": "+91 98765 43210",
            }
            with self.assertRaises(AuthenticationError) as raised:
                self.service.create(self.context, InvitationCreate(**{**base, **changes}))
            return raised.exception.code

        self.assertEqual(invite(email="ravi@gmail.com"), "LOGIN_NOT_INTERNAL")
        self.assertEqual(invite(notification_email=None), "GMAIL_REQUIRED")
        self.assertEqual(invite(notification_email="ravi@adverseindia.com"), "GMAIL_IS_INTERNAL")
        self.repository.gmail_in_use.return_value = "someone@adverseindia.com"
        self.assertEqual(invite(), "GMAIL_IN_USE")
        self.repository.gmail_in_use.return_value = None
        self.repository.department_ok.return_value = False
        self.assertEqual(invite(department_id=uuid4()), "DEPARTMENT_NOT_FOUND")
        send_email.assert_not_called()

    @patch("app.services.invitation_service.validate_user_action_access", return_value=True)
    @patch("app.services.invitation_service.email_service.send_invitation")
    def test_staff_details_reach_the_repository(self, send_email: MagicMock, _: MagicMock) -> None:
        from datetime import date

        department = uuid4()
        self.service.create(
            self.context,
            InvitationCreate(
                email="ravi.kumar@adverseindia.com",
                notification_email="ravi@gmail.com",
                name="Ravi Kumar",
                phone_number="+91 98765 43210",
                designation="  Video Editor ",
                department_id=department,
                joining_date=date(2026, 12, 1),
            ),
        )
        kwargs = self.repository.create.call_args.kwargs
        self.assertEqual(kwargs["designation"], "Video Editor")
        self.assertEqual(kwargs["department_id"], department)
        self.assertEqual(kwargs["joining_date"], date(2026, 12, 1))
        with self.assertRaises(ValueError):  # clients do not take staff details
            InvitationCreate(
                email="brand@adverseindia.com",
                notification_email="brand@gmail.com",
                name="Brand",
                phone_number="+91 98765 43210",
                role_code="COMPANY_CLIENT",
                designation="Owner",
            )

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
