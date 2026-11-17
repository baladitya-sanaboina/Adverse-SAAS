import logging
import smtplib
from email.message import EmailMessage
from html import escape
from typing import Protocol

from app.core.settings import settings

logger = logging.getLogger(__name__)


def branded_email_html(
    *,
    eyebrow: str,
    title: str,
    description: str,
    action_label: str,
    action_url: str,
    expiry_minutes: int,
) -> str:
    """Render a light-mode, email-client-safe Adverse transactional template."""
    safe_url = escape(action_url, quote=True)
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="color-scheme" content="light">
    <meta name="supported-color-schemes" content="light">
    <title>{escape(title)}</title>
  </head>
  <body style="margin:0;padding:0;background:#F4FAFF;color:#241f2b;font-family:Poppins,Arial,Helvetica,sans-serif;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#F4FAFF;">
      <tr>
        <td align="center" style="padding:40px 16px;">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width:620px;">
            <tr>
              <td style="padding:0 4px 18px;color:#0876ED;font-size:22px;font-weight:800;letter-spacing:-0.5px;">
                Adverse
              </td>
            </tr>
            <tr>
              <td style="overflow:hidden;border:1px solid #ded6e8;border-radius:20px;background:#ffffff;box-shadow:0 16px 44px rgba(55,38,72,.08);">
                <div style="height:7px;background:#0876ED;font-size:0;line-height:0;">&nbsp;</div>
                <div style="padding:42px 42px 38px;">
                  <div style="display:inline-block;margin-bottom:20px;padding:7px 11px;border-radius:999px;background:#f1ebf7;color:#0876ED;font-size:11px;font-weight:800;letter-spacing:1.2px;text-transform:uppercase;">
                    {escape(eyebrow)}
                  </div>
                  <h1 style="margin:0 0 14px;color:#241f2b;font-size:30px;line-height:1.25;font-weight:800;letter-spacing:-.7px;">
                    {escape(title)}
                  </h1>
                  <p style="margin:0 0 22px;color:#67788E;font-size:15px;line-height:1.75;">
                    {escape(description)}
                  </p>
                  <div style="margin:0 0 26px;padding:13px 15px;border:1px solid #e5deed;border-radius:12px;background:#faf8fc;color:#5f5668;font-size:13px;line-height:1.5;">
                    This secure, single-use link expires in <strong style="color:#0876ED;">{expiry_minutes} minutes</strong>.
                  </div>
                  <table role="presentation" cellspacing="0" cellpadding="0" border="0">
                    <tr>
                      <td style="border-radius:11px;background:#0876ED;">
                        <a href="{safe_url}" style="display:inline-block;padding:14px 24px;color:#ffffff;text-decoration:none;font-size:14px;font-weight:800;">
                          {escape(action_label)}
                        </a>
                      </td>
                    </tr>
                  </table>
                  <div style="margin:30px 0 0;padding-top:24px;border-top:1px solid #eee9f3;">
                    <p style="margin:0 0 9px;color:#67788E;font-size:12px;line-height:1.6;">
                      If the button does not work, copy and paste this link into your browser:
                    </p>
                    <p style="margin:0;overflow-wrap:anywhere;word-break:break-all;color:#0876ED;font-size:11px;line-height:1.6;">
                      <a href="{safe_url}" style="color:#0876ED;text-decoration:underline;">{safe_url}</a>
                    </p>
                  </div>
                </div>
              </td>
            </tr>
            <tr>
              <td style="padding:18px 12px 0;text-align:center;color:#7C8DA3;font-size:11px;line-height:1.7;">
                If you did not request this action, you can safely ignore this email.<br>
                © Adverse · Secure business management
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""


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
    safe_url = escape(action_url, quote=True) if action_url else None
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="color-scheme" content="light">
    <meta name="supported-color-schemes" content="light">
    <title>{escape(title)}</title>
  </head>
  <body style="margin:0;padding:0;background:#F4FAFF;color:#241f2b;font-family:Poppins,Arial,Helvetica,sans-serif;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#F4FAFF;">
      <tr>
        <td align="center" style="padding:40px 16px;">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width:620px;">
            <tr>
              <td style="padding:0 4px 18px;color:#0876ED;font-size:22px;font-weight:800;letter-spacing:-0.5px;">
                Adverse
              </td>
            </tr>
            <tr>
              <td style="overflow:hidden;border:1px solid #ded6e8;border-radius:20px;background:#ffffff;box-shadow:0 16px 44px rgba(55,38,72,.08);">
                <div style="height:7px;background:#0876ED;font-size:0;line-height:0;">&nbsp;</div>
                <div style="padding:42px 42px 38px;">
                  <div style="display:inline-block;margin-bottom:20px;padding:7px 11px;border-radius:999px;background:#f1ebf7;color:#0876ED;font-size:11px;font-weight:800;letter-spacing:1.2px;text-transform:uppercase;">
                    {escape(eyebrow)}
                  </div>
                  <h1 style="margin:0 0 14px;color:#241f2b;font-size:30px;line-height:1.25;font-weight:800;letter-spacing:-.7px;">
                    {escape(title)}
                  </h1>
                  <p style="margin:0 0 22px;color:#67788E;font-size:15px;line-height:1.75;">
                    {escape(description)}
                  </p>
                  <div style="margin:0 0 22px;padding:22px;border-radius:18px;background:#f6f1fb;border:1px dashed #d7c7ec;text-align:center;">
                    <div style="margin-bottom:8px;color:#7B8DA7;font-size:11px;font-weight:700;letter-spacing:1.4px;text-transform:uppercase;">One-time code</div>
                    <div style="color:#241f2b;font-size:36px;font-weight:800;letter-spacing:10px;font-family:Menlo,Consolas,monospace;">{escape(code)}</div>
                  </div>
                  <div style="padding:13px 15px;border:1px solid #e5deed;border-radius:12px;background:#faf8fc;color:#5f5668;font-size:13px;line-height:1.5;">
                    This secure code expires in <strong style="color:#0876ED;">{expiry_minutes} minutes</strong>.
                  </div>
                  {f'''<div style="margin-top:22px;">
                    <table role="presentation" cellspacing="0" cellpadding="0" border="0">
                      <tr>
                        <td style="border-radius:11px;background:#0876ED;">
                          <a href="{safe_url}" style="display:inline-block;padding:14px 24px;color:#ffffff;text-decoration:none;font-size:14px;font-weight:800;">
                            {escape(action_label or 'Open verification page')}
                          </a>
                        </td>
                      </tr>
                    </table>
                    <div style="margin:18px 0 0;color:#67788E;font-size:12px;line-height:1.6;">
                      You can also tap the button above to open the correct workspace confirmation page automatically.
                    </div>
                    <div style="margin:12px 0 0;overflow-wrap:anywhere;word-break:break-all;color:#0876ED;font-size:11px;line-height:1.6;">
                      <a href="{safe_url}" style="color:#0876ED;text-decoration:underline;">{safe_url}</a>
                    </div>
                  </div>''' if safe_url else ''}
                </div>
              </td>
            </tr>
            <tr>
              <td style="padding:18px 12px 0;text-align:center;color:#7C8DA3;font-size:11px;line-height:1.7;">
                If you did not request this action, you can safely ignore this email.<br>
                © Adverse · Secure business management
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""


class PasswordResetEmailSender(Protocol):
    def send_password_reset(self, email: str, reset_code: str) -> None: ...


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
        return [
            address
            for _, address in found
            if address.lower() not in TEST_ACCOUNT_EMAILS and not address.lower().endswith(reserved)
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

    def send_password_reset(self, email: str, reset_code: str) -> None:
        if not settings.smtp_host:
            logger.warning("Development password reset code for %s: %s", email, reset_code)
            return

        message = EmailMessage()
        message["Subject"] = "Reset your Adverse password"
        message["From"] = settings.smtp_from_email or settings.smtp_username
        message["To"] = email
        message.set_content(
            "Use this 6-digit code to reset your Adverse password. "
            f"It expires in {settings.password_reset_expiry_minutes} minutes.\n\n{reset_code}"
        )
        message.add_alternative(
            branded_code_email_html(
                eyebrow="Account security",
                title="Reset your password",
                description=(
                    "We received a request to update the password for your Adverse account. "
                    "Enter this one-time code to choose a new, secure password."
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
                description=(
                    "Your workspace is almost ready. Confirm this email address to activate "
                    "your account and continue to Adverse."
                ),
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
                    f"Your {company_name} workspace ({company_code}) is ready. "
                    "Verify your email using the separate activation message, then sign in. "
                    "For security, your password is never included in email."
                ),
                action_label="Open Adverse",
                action_url=login_url,
                expiry_minutes=settings.email_verification_expiry_minutes,
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
                title=f"Set up your {company_name} access",
                description=(
                    f"Your company administrator prepared access for the Adverse login {login_identity} in {company_name}. "
                    "Set your password to activate the account and continue."
                ),
                action_label="Set up access",
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
    ) -> None:
        message = EmailMessage()
        message["Subject"] = f"Your {company_name} Adverse login is ready"
        message["From"] = settings.smtp_from_email or settings.smtp_username
        message["To"] = email
        message.set_content(
            f"Your {company_name} account is ready. Sign in with {login_email} at {login_url}. "
            "Use the password you created during setup; for security, it is never included in email."
        )
        message.add_alternative(
            branded_email_html(
                eyebrow="Account ready",
                title=f"Your {company_name} login is ready",
                description=(
                    f"Your Adverse login is {login_email}. Use the password you created during setup and continue to your workspace. "
                    "For security, your password is never included in email."
                ),
                action_label="Open workspace login",
                action_url=login_url,
                expiry_minutes=settings.invitation_expiry_hours * 60,
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
        safe = {
            key: escape(value)
            for key, value in {
                "company": company_name,
                "client": client_name,
                "code": invoice_code,
                "amount": amount,
                "period": period,
                "url": portal_url,
            }.items()
        }
        message.add_alternative(
            f"""<!doctype html><html lang="en"><body style="margin:0;padding:24px;background:#f4f7fb;
font-family:Arial,Helvetica,sans-serif;color:#0f172a">
<table role="presentation" width="100%" style="max-width:560px;margin:0 auto;background:#ffffff;
border:1px solid #e2e8f0;border-radius:14px;border-top:4px solid #0876ED">
<tr><td style="padding:28px 28px 8px"><p style="margin:0;color:#0876ED;font-size:12px;
font-weight:700;letter-spacing:.08em;text-transform:uppercase">Invoice {safe["code"]}</p>
<h1 style="margin:8px 0 6px;font-size:22px">{safe["amount"]}</h1>
<p style="margin:0;color:#64748b;font-size:14px">Work delivered {safe["period"]}</p></td></tr>
<tr><td style="padding:16px 28px;font-size:14px;line-height:1.6">Hello {safe["client"]},<br>
The invoice is attached as a PDF. Every video in this period is listed with its date and amount.
</td></tr>
<tr><td style="padding:4px 28px 28px"><a href="{safe["url"]}" style="display:inline-block;
padding:12px 18px;border-radius:9px;background:#0876ED;color:#ffffff;text-decoration:none;
font-weight:700;font-size:14px">Open client portal</a>
<p style="margin:18px 0 0;color:#64748b;font-size:12px">{safe["company"]}</p></td></tr>
</table></body></html>""",
            subtype="html",
        )
        message.add_attachment(pdf, maintype="application", subtype="pdf", filename=filename)
        self._send(message)


email_service = EmailService()
