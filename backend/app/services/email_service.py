import logging
import smtplib
from email.message import EmailMessage
from typing import Protocol

from app.core.settings import settings
from app.services.mail_templates import render_mail

logger = logging.getLogger(__name__)


def _expiry_text(minutes: int) -> str:
    if minutes % (24 * 60) == 0:
        days = minutes // (24 * 60)
        return f"{days} day{'s' if days != 1 else ''}"
    if minutes % 60 == 0:
        hours = minutes // 60
        return f"{hours} hour{'s' if hours != 1 else ''}"
    return f"{minutes} minutes"


def branded_email_html(
    *,
    eyebrow: str,
    title: str,
    description: str,
    action_label: str,
    action_url: str,
    expiry_minutes: int | None,
    details: list[tuple[str, str]] | None = None,
) -> str:
    """An account mail in the shared Adverse layout (mail_templates.render_mail). `details` are
    label/value rows (e.g. the login and password); a link that expires says so under the button
    and carries the "did not ask for this" note. `eyebrow` is the small label in the header."""
    expires = expiry_minutes is not None
    return render_mail(
        title=title,
        eyebrow=eyebrow,
        lines=[description],
        rows=details or (),
        monospace_rows=bool(details),
        action_label=action_label,
        action_url=action_url,
        after=(
            [f"This link works once and expires in {_expiry_text(expiry_minutes)}."]
            if expiry_minutes is not None
            else ()
        ),
        show_link=True,
        footnote="If you were not expecting this mail, you can ignore it." if expires else None,
    )


def branded_code_email_html(
    *,
    eyebrow: str,
    title: str,
    description: str,
    code: str,
    expiry_minutes: int,
    action_label: str | None = None,
    action_url: str | None = None,
) -> str:
    """A one-time code mail in the shared Adverse layout."""
    return render_mail(
        title=title,
        eyebrow=eyebrow,
        lines=[description],
        code=code,
        action_label=action_label,
        action_url=action_url,
        after=[f"The code works once and expires in {_expiry_text(expiry_minutes)}."],
        footnote="If you did not ask for this code, you can ignore this mail; nothing changes.",
    )


class PasswordResetEmailSender(Protocol):
    def send_password_reset(
        self, email: str, reset_code: str, login_email: str | None = None
    ) -> None: ...


class VerificationEmailSender(Protocol):
    def send_verification(
        self, email: str, verification_code: str, *, verification_url: str | None = None
    ) -> None: ...


class EmailService:
    """Outgoing mail (owner decisions 2026-11-15): only mail that leaves the company goes by
    SMTP; work inside the company uses the in-app mailbox. Seeded test logins never get real
    mail, and the same mail about the same thing is not repeated within a short window."""

    @staticmethod
    def _sender() -> str:
        address = settings.smtp_from_email or settings.smtp_username
        return f"{settings.smtp_from_name} <{address}>" if settings.smtp_from_name else address

    @staticmethod
    def _real_recipients(message: EmailMessage) -> list[str]:
        from email.utils import getaddresses

        from app.services.development_test_credentials_service import TEST_ACCOUNT_EMAILS

        found = getaddresses(message.get_all("To", []) + message.get_all("Cc", []))
        # Reserved test domains never deliver anywhere; skip them instead of bouncing.
        reserved = ("@example.com", "@example.org", "@example.net", ".test", ".invalid", ".example")
        # Internal logins (name@adverseindia.com) exist only inside the app: never mail them.
        return [
            address
            for _, address in found
            if address.lower() not in TEST_ACCOUNT_EMAILS
            and not address.lower().endswith(reserved)
            and not settings.is_internal_email(address)
        ]

    @staticmethod
    def _first_time(key: str | None) -> bool:
        """False when this mail was already sent within the repeat window."""
        if not key or settings.mail_repeat_window_minutes <= 0:
            return True
        try:
            from app.services.realtime import _redis

            return bool(
                _redis().set(
                    f"mail:once:{key}", "1", nx=True, ex=settings.mail_repeat_window_minutes * 60
                )
            )
        except Exception:  # noqa: BLE001 - without Redis, send rather than lose the mail
            return True

    def _send(self, message: EmailMessage, *, once_key: str | None = None) -> None:
        if not settings.mail_delivery_enabled:
            logger.info("Mail '%s' not sent: delivery is off on this site.", message["Subject"])
            return
        recipients = self._real_recipients(message)
        if not recipients:
            logger.info(
                "Mail '%s' not sent: only test accounts were addressed.", message["Subject"]
            )
            return
        if not self._first_time(once_key):
            logger.info("Mail '%s' skipped: already sent recently.", message["Subject"])
            return
        if "From" in message:
            message.replace_header("From", self._sender())
        else:
            message["From"] = self._sender()
        host, port = settings.smtp_host, settings.smtp_port
        username, password = settings.smtp_username, settings.smtp_password.get_secret_value()
        encryption = "STARTTLS" if settings.smtp_use_tls else "NONE"
        if not username:
            # No account in backend/.env: use the platform's SMTP settings, if any.
            try:
                from app.repositories.platform_settings_repository import (
                    PlatformSettingsRepository,
                )
                from app.services.platform_settings_service import platform_settings_service

                platform = PlatformSettingsRepository().get()
                host, port = platform.smtp_host, platform.smtp_port
                username = platform.smtp_username
                password = platform_settings_service.decrypt_password(
                    platform.smtp_password_encrypted
                )
                encryption = platform.smtp_encryption
                message.replace_header(
                    "From", f"{platform.smtp_sender_name} <{platform.smtp_sender_email}>"
                )
            except Exception:
                logger.warning(
                    "Using environment SMTP configuration; platform settings unavailable."
                )
        client_type = smtplib.SMTP_SSL if encryption == "SSL" else smtplib.SMTP
        with client_type(host, port, timeout=15) as client:
            if encryption == "STARTTLS":
                client.starttls()
            if username:
                client.login(username, password)
            client.send_message(message, to_addrs=recipients)

    def is_ready(self) -> bool:
        if not settings.smtp_host:
            return False
        try:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=3) as client:
                return client.noop()[0] == 250
        except (OSError, smtplib.SMTPException):
            return False

    def send_password_reset(
        self, email: str, reset_code: str, login_email: str | None = None
    ) -> None:
        """email: where the code goes (their Gmail); login_email: the account it is for."""
        if not settings.smtp_host:
            logger.warning("Development password reset code for %s: %s", email, reset_code)
            return
        login = login_email or email
        message = EmailMessage()
        message["Subject"] = "Reset your Adverse password"
        message["From"] = settings.smtp_from_email or settings.smtp_username
        message["To"] = email
        message.set_content(
            f"Use this 6-digit code to reset the password of your Adverse login {login}. "
            f"It expires in {settings.password_reset_expiry_minutes} minutes.\n\n{reset_code}"
        )
        message.add_alternative(
            branded_code_email_html(
                eyebrow="Account security",
                title="Reset your password",
                description=(
                    f"Use the code below to set a new password for your Adverse login {login}."
                ),
                code=reset_code,
                expiry_minutes=settings.password_reset_expiry_minutes,
            ),
            subtype="html",
        )
        self._send(message)

    def send_verification(
        self, email: str, verification_code: str, *, verification_url: str | None = None
    ) -> None:
        if not settings.smtp_host:
            logger.warning(
                "Development email verification code for %s: %s", email, verification_code
            )
            return
        message = EmailMessage()
        message["Subject"] = "Verify your Adverse email"
        message["From"] = settings.smtp_from_email or settings.smtp_username
        message["To"] = email
        if verification_url:
            message.set_content(
                "Use this 6-digit code to activate your Adverse account, or open the secure "
                f"verification link for your workspace: {verification_url}\n\n"
                f"This code expires in {settings.email_verification_expiry_minutes} minutes.\n\n"
                f"{verification_code}"
            )
        else:
            message.set_content(
                "Use this 6-digit code to activate your Adverse account. "
                f"It expires in {settings.email_verification_expiry_minutes} minutes.\n\n{verification_code}"
            )
        message.add_alternative(
            branded_code_email_html(
                eyebrow="Welcome to Adverse",
                title="Verify your email address",
                description="Enter this code in Adverse to confirm your email and activate your account.",
                code=verification_code,
                expiry_minutes=settings.email_verification_expiry_minutes,
                action_label="Verify your email",
                action_url=verification_url,
            ),
            subtype="html",
        )
        self._send(message)

    def send_company_welcome(
        self, email: str, *, admin_name: str, company_name: str, company_code: str
    ) -> None:
        """Send onboarding instructions without ever disclosing the submitted password."""
        origins = settings.allowed_origins
        login_url = origins[0]
        message = EmailMessage()
        message["Subject"] = f"Welcome to {company_name} on Adverse"
        message["From"] = settings.smtp_from_email or settings.smtp_username
        message["To"] = email
        message.set_content(
            f"Hello {admin_name}, your {company_name} workspace ({company_code}) is ready. "
            f"Verify your email, then sign in at {login_url}."
        )
        message.add_alternative(
            branded_email_html(
                eyebrow="Workspace ready",
                title=f"Welcome, {admin_name}",
                description=(
                    f"Your {company_name} workspace ({company_code}) is ready. Verify your email "
                    "with the code we sent in a separate mail, then sign in."
                ),
                action_label="Open Adverse",
                action_url=login_url,
                expiry_minutes=None,
            ),
            subtype="html",
        )
        self._send(message)

    def send_invitation(
        self,
        email: str,
        *,
        company_name: str,
        invitation_url: str,
        login_email: str | None = None,
    ) -> None:
        login_identity = login_email or email
        message = EmailMessage()
        message["Subject"] = f"Set up your {company_name} access on Adverse"
        message["From"] = settings.smtp_from_email or settings.smtp_username
        message["To"] = email
        message.set_content(
            f"Your {company_name} access is almost ready. "
            f"Use this secure link to set your password and activate the Adverse login {login_identity}: {invitation_url}"
        )
        message.add_alternative(
            branded_email_html(
                eyebrow="Account setup",
                title=f"You're invited to {company_name}",
                description=(
                    f"{company_name} has created an Adverse account for you. Set your password to "
                    "start using it."
                ),
                details=[("Your login", login_identity)],
                action_label="Set your password",
                action_url=invitation_url,
                expiry_minutes=settings.invitation_expiry_hours * 60,
            ),
            subtype="html",
        )
        self._send(message)

    def send_account_ready(
        self,
        email: str,
        *,
        company_name: str,
        login_email: str,
        login_url: str,
        password: str | None = None,
        gmail_login: str | None = None,
    ) -> None:
        """The welcome mail to their Gmail once the account is set up (owner request
        2026-11-19): the internal login the admin gave them and, when given, the password they
        chose, so they can sign in straight away. gmail_login: clients also sign in with their
        Gmail, so it is shown as the login and the internal address as their Adverse ID."""
        message = EmailMessage()
        message["Subject"] = f"Welcome to {company_name}: your Adverse login"
        message["From"] = settings.smtp_from_email or settings.smtp_username
        message["To"] = email
        lines = [f"Welcome to {company_name}. Your Adverse account is ready.", ""]
        if gmail_login:
            lines += [f"Login: {gmail_login} (or your Adverse ID)", f"Adverse ID: {login_email}"]
        else:
            lines.append(f"Login: {login_email}")
        if password:
            lines.append(f"Password: {password}")
        lines += [
            "",
            f"Sign in at {login_url}",
            "",
            "Keep this mail private. You can change your password anytime from your profile;"
            " if you forget it, use Forgot password and the code comes to this Gmail.",
        ]
        message.set_content("\n".join(lines))
        details = (
            [("Login", gmail_login), ("Adverse ID", login_email)]
            if gmail_login
            else [("Login", login_email)]
        ) + ([("Password", password)] if password else [])
        message.add_alternative(
            branded_email_html(
                eyebrow="Welcome",
                title=f"Welcome to {company_name}",
                description=(
                    "Your account is ready. Sign in with your Gmail or your Adverse ID."
                    if gmail_login
                    else "Your account is ready. Sign in with the details below."
                ),
                action_label="Sign in to Adverse",
                action_url=login_url,
                expiry_minutes=None,
                details=details,
            ),
            subtype="html",
        )
        self._send(message)

    def send_invoice(
        self,
        email: str,
        *,
        company_name: str,
        client_name: str,
        invoice_code: str,
        amount: str,
        period: str,
        portal_url: str,
        pdf: bytes,
        filename: str,
    ) -> None:
        """Invoice email with the PDF attached (Phase 11)."""
        message = EmailMessage()
        message["Subject"] = f"Invoice {invoice_code} from {company_name}"
        message["From"] = settings.smtp_from_email or settings.smtp_username
        message["To"] = email
        message.set_content(
            f"Hello {client_name},\n\nPlease find attached invoice {invoice_code} for {amount} "
            f"covering work delivered {period}.\n\nYou can also view all your invoices and "
            f"payments in your client portal: {portal_url}\n\nThank you,\n{company_name}"
        )
        message.add_alternative(
            render_mail(
                title=f"Invoice {invoice_code}",
                greeting=f"Hello {client_name},",
                lines=[
                    f"Please find attached invoice {invoice_code} for the work delivered "
                    f"{period}. Each video is listed in the PDF with its date and amount."
                ],
                rows=[("Invoice", invoice_code), ("Period", period)],
                highlight=("Amount due", amount),
                eyebrow="Invoice",
                action_label="View in your client portal",
                action_url=portal_url,
                after=["If anything looks wrong, just reply to this mail and we will sort it out."],
                sign_off=company_name,
                company=company_name,
            ),
            subtype="html",
        )
        message.add_attachment(pdf, maintype="application", subtype="pdf", filename=filename)
        self._send(message)


email_service = EmailService()
