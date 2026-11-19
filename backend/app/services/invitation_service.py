import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.core.settings import settings
from app.repositories.invitation_repository import (
    InvitationConflict,
    InvitationRecord,
    InvitationRepository,
)
from app.schemas.authentication import AuthContext
from app.schemas.invitations import (
    InvitationAcceptedResponse,
    InvitationAcceptRequest,
    InvitationActionResponse,
    InvitationCreate,
    InvitationListResponse,
    InvitationResponse,
    InvitationValidationResponse,
)
from app.services.authentication_service import AuthenticationError
from app.services.email_service import email_service
from app.services.password_service import hash_password
from app.services.permission_service import validate_user_action_access

logger = logging.getLogger(__name__)


def invitation_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class InvitationService:
    def __init__(self, repository: InvitationRepository | None = None):
        self.repository = repository or InvitationRepository()

    @staticmethod
    def _authorize(context: AuthContext, action: str) -> UUID:
        if context.role != "COMPANY_ADMIN" or context.company_id is None:
            raise AuthenticationError(
                403, "COMPANY_ADMIN_REQUIRED", "Company Admin access is required."
            )
        permission = "MANAGE" if action in {"RESEND", "REVOKE"} else action
        if not validate_user_action_access(
            str(context.user_id), context.role, "INVITATIONS", permission
        ):
            raise AuthenticationError(
                403, "INVITATION_PERMISSION_REQUIRED", "Invitation permission is required."
            )
        return context.company_id

    @staticmethod
    def _response(record: InvitationRecord) -> InvitationResponse:
        return InvitationResponse(**record.__dict__)

    @staticmethod
    def _login_url(role_code: str) -> str:
        return settings.login_url(role_code)

    @staticmethod
    def _new_token() -> tuple[str, str, datetime]:
        token = secrets.token_urlsafe(48)
        return (
            token,
            invitation_token_hash(token),
            datetime.now(UTC) + timedelta(hours=settings.invitation_expiry_hours),
        )

    def _check_addresses(self, company_id: UUID, request: InvitationCreate) -> None:
        """Owner request 2026-11-19: the login is an internal address (name@adverseindia.com)
        that only works inside the app; their own Gmail gets the setup link and outside mail."""
        login = str(request.email).lower()
        gmail = str(request.notification_email).lower() if request.notification_email else ""
        domain = settings.internal_email_domain.strip().lstrip("@")
        if domain and not settings.is_internal_email(login):
            raise AuthenticationError(
                422,
                "LOGIN_NOT_INTERNAL",
                f"The login must be an internal address ending in @{domain}.",
            )
        if domain and not gmail:
            raise AuthenticationError(
                422, "GMAIL_REQUIRED", "Add their Gmail: the setup link goes there."
            )
        if gmail and settings.is_internal_email(gmail):
            raise AuthenticationError(
                422,
                "GMAIL_IS_INTERNAL",
                f"Their Gmail must be an outside address, not @{domain}.",
            )
        if gmail and gmail == login:
            raise AuthenticationError(
                422, "GMAIL_SAME_AS_LOGIN", "The Gmail and the login must be different."
            )
        if gmail:
            other = self.repository.gmail_in_use(gmail, login)
            if other:
                raise AuthenticationError(
                    409, "GMAIL_IN_USE", f"This Gmail is already used by the login {other}."
                )
        if request.department_id and not self.repository.department_ok(
            company_id, request.department_id
        ):
            raise AuthenticationError(404, "DEPARTMENT_NOT_FOUND", "Department was not found.")

    def create(self, context: AuthContext, request: InvitationCreate) -> InvitationResponse:
        company_id = self._authorize(context, "CREATE")
        self._check_addresses(company_id, request)
        token, token_hash, expires_at = self._new_token()
        invited_name = request.name.strip() if request.name else None
        provisioned_password_hash = (
            hash_password(secrets.token_urlsafe(32)) if invited_name is not None else None
        )
        try:
            record = self.repository.create(
                company_id,
                context.user_id,
                str(request.email).lower(),
                str(request.notification_email or request.email).lower(),
                token_hash,
                expires_at,
                request.role_code,
                invited_name,
                request.phone_number,
                provisioned_password_hash,
                request.client_id,
                designation=request.designation,
                department_id=request.department_id,
                joining_date=request.joining_date,
            )
        except InvitationConflict as error:
            code = str(error)
            if code == "CLIENT_NOT_FOUND":
                raise AuthenticationError(404, code, "Client was not found.") from error
            detail = (
                "User with this email already exists."
                if code == "USER_EXISTS"
                else "A pending invitation already exists."
            )
            raise AuthenticationError(409, code, detail) from error
        email_service.send_invitation(
            record.notification_email,
            company_name=record.company_name,
            invitation_url=settings.invitation_url(record.role_code, token),
            login_email=record.email,
        )
        return self._response(record)

    def list(self, context: AuthContext) -> InvitationListResponse:
        company_id = self._authorize(context, "VIEW")
        records = self.repository.list(company_id)
        return InvitationListResponse(
            items=[self._response(item) for item in records], total=len(records)
        )

    def get(self, context: AuthContext, invitation_id: UUID) -> InvitationResponse:
        company_id = self._authorize(context, "VIEW")
        record = self.repository.get(company_id, invitation_id)
        if not record:
            raise AuthenticationError(404, "INVITATION_NOT_FOUND", "Invitation was not found.")
        return self._response(record)

    def validate(self, token: str) -> InvitationValidationResponse:
        found = self.repository.find_by_hash(invitation_token_hash(token))
        if not found:
            self.repository.audit_validation_failure(None, "INVALID_TOKEN")
            raise AuthenticationError(400, "INVALID_INVITATION", "Invitation link is invalid.")
        record, _, _, _ = found
        if record.status == "EXPIRED":
            self.repository.audit_validation_failure(found, "EXPIRED_TOKEN")
            raise AuthenticationError(410, "INVITATION_EXPIRED", "Invitation has expired.")
        if record.status != "PENDING":
            self.repository.audit_validation_failure(found, f"TOKEN_REPLAY_{record.status}")
            raise AuthenticationError(
                400, f"INVITATION_{record.status}", "Invitation is no longer available."
            )
        return InvitationValidationResponse(
            valid=True,
            email=record.email,
            company_name=record.company_name,
            role_code=record.role_code,
            login_url=self._login_url(record.role_code),
            expires_at=record.expires_at,
        )

    def resend(self, context: AuthContext, invitation_id: UUID) -> InvitationActionResponse:
        company_id = self._authorize(context, "RESEND")
        token, token_hash, expires_at = self._new_token()
        record = self.repository.resend(
            company_id, invitation_id, context.user_id, token_hash, expires_at
        )
        if not record:
            raise AuthenticationError(
                404, "INVITATION_NOT_RESENDABLE", "Invitation cannot be resent."
            )
        email_service.send_invitation(
            record.notification_email,
            company_name=record.company_name,
            invitation_url=settings.invitation_url(record.role_code, token),
            login_email=record.email,
        )
        return InvitationActionResponse(message="Invitation resent successfully.")

    def revoke(self, context: AuthContext, invitation_id: UUID) -> InvitationActionResponse:
        company_id = self._authorize(context, "REVOKE")
        if not self.repository.revoke(company_id, invitation_id, context.user_id):
            raise AuthenticationError(
                404, "INVITATION_NOT_REVOKABLE", "Invitation cannot be revoked."
            )
        return InvitationActionResponse(message="Invitation revoked successfully.")

    def accept(self, request: InvitationAcceptRequest) -> InvitationAcceptedResponse:
        token_hash = invitation_token_hash(request.token)
        self.validate(request.token)
        try:
            accepted = self.repository.accept(
                token_hash, request.name, hash_password(request.password.get_secret_value())
            )
        except InvitationConflict as error:
            if str(error) == "CLIENT_NOT_FOUND":
                raise AuthenticationError(
                    404,
                    "CLIENT_NOT_FOUND",
                    "The linked client profile is no longer available.",
                ) from error
            raise AuthenticationError(
                409, "USER_EXISTS", "User with this email already exists."
            ) from error
        if not accepted:
            raise AuthenticationError(
                400, "INVALID_INVITATION", "Invitation is no longer available."
            )
        login_email, notification_email, company_name, role_code, *created = accepted
        try:
            # To their Gmail: the login is ready (never to the internal address).
            email_service.send_account_ready(
                notification_email,
                company_name=company_name,
                login_email=login_email,
                login_url=self._login_url(role_code),
            )
        except Exception:
            logger.exception("Accepted invitation confirmation email failed for %s", login_email)
        if len(created) == 2:
            self._welcome(created[0], created[1], login_email, company_name, role_code)
        return InvitationAcceptedResponse(
            email=login_email,
            company_name=company_name,
            role_code=role_code,
            login_url=self._login_url(role_code),
        )

    @staticmethod
    def _welcome(
        user_id: UUID, company_id: UUID, login_email: str, company_name: str, role_code: str
    ) -> None:
        """The first mail in their internal mailbox: work mail arrives here from now on."""
        from app.services.mail_service import mail_service

        staff = role_code != "COMPANY_CLIENT"
        body = [
            f"Welcome to {company_name}.",
            "",
            f"Your login is {login_email}. This mailbox is where work mail arrives from now on:"
            + (" tasks, changes, payments and meetings." if staff else " updates from the team."),
            "Password resets and account mail go to your Gmail.",
        ]
        mail_service.system(
            company_id,
            [user_id],
            f"Welcome to {company_name}",
            "\n".join(body),
            link="/dashboard",
            kind="WELCOME",
            notify=True,
        )

    def is_ready(self) -> bool:
        return self.repository.is_ready()


invitation_service = InvitationService()
