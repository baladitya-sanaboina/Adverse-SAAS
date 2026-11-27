import unittest
from unittest.mock import patch

from app.core.settings import settings
from app.services.email_service import EmailService


class EmailTemplateTests(unittest.TestCase):
    def assert_code_message(self, message, expected_code: str, expected_copy: str) -> None:
        self.assertTrue(message.is_multipart())
        plain = message.get_body(preferencelist=("plain",)).get_content()
        html = message.get_body(preferencelist=("html",)).get_content()
        self.assertIn(expected_code, plain)
        self.assertIn(expected_code, html)
        self.assertIn(expected_copy, html)
        self.assertIn("Adverse", html)
        self.assertIn("#0876ed", html)
        self.assertIn('name="color-scheme" content="light only"', html)

    @patch.object(settings, "smtp_host", "mailpit")
    def test_verification_email_has_plain_and_branded_html_parts(self) -> None:
        service = EmailService()
        code = "482951"
        verification_url = (
            "https://employee.adverseindia.com/verify-email?email=user%40example.com&otp=482951"
        )
        with patch.object(service, "_send") as send:
            service.send_verification("user@example.com", code, verification_url=verification_url)
        message = send.call_args.args[0]
        self.assert_code_message(message, code, "Verify your email address")
        plain = message.get_body(preferencelist=("plain",)).get_content()
        html = message.get_body(preferencelist=("html",)).get_content()
        self.assertIn(verification_url, plain)
        self.assertIn(verification_url.replace("&", "&amp;"), html)

    @patch.object(settings, "smtp_host", "mailpit")
    def test_password_reset_email_has_plain_and_branded_html_parts(self) -> None:
        service = EmailService()
        code = "937114"
        with patch.object(service, "_send") as send:
            service.send_password_reset("user@example.com", code)
        self.assert_code_message(send.call_args.args[0], code, "Reset your password")

    @patch.object(settings, "smtp_host", "mailpit")
    def test_company_welcome_contains_context_but_never_password(self) -> None:
        service = EmailService()
        with patch.object(service, "_send") as send:
            service.send_company_welcome(
                "admin@example.com",
                admin_name="Asha Rao",
                company_name="Acme Operations",
                company_code="ACME_OPS",
            )
        message = send.call_args.args[0]
        plain = message.get_body(preferencelist=("plain",)).get_content()
        html = message.get_body(preferencelist=("html",)).get_content()
        self.assertIn("Acme Operations", plain)
        self.assertIn("ACME_OPS", html)
        self.assertNotIn("expires", html)  # a plain sign-in link, not a one-time link
        self.assertNotIn("StrongPass", message.as_string())

    @patch.object(settings, "smtp_host", "mailpit")
    def test_invitation_email_includes_internal_login_email(self) -> None:
        service = EmailService()
        with patch.object(service, "_send") as send:
            service.send_invitation(
                "person@gmail.com",
                company_name="Acme Operations",
                invitation_url="https://employee.adverseindia.com/invitations/accept?token=abc",
                login_email="employee@adverseindia.com",
            )
        message = send.call_args.args[0]
        plain = message.get_body(preferencelist=("plain",)).get_content()
        html = message.get_body(preferencelist=("html",)).get_content()
        self.assertIn("employee@adverseindia.com", plain)
        self.assertIn("employee@adverseindia.com", html)
        self.assertIn("Acme Operations", plain)

    @patch.object(settings, "smtp_host", "mailpit")
    def test_welcome_email_carries_the_login_and_password(self) -> None:
        """Owner request 2026-11-19: the welcome mail to their Gmail has the internal login
        the admin gave them and the password they chose, so they can sign in straight away."""
        service = EmailService()
        with patch.object(service, "_send") as send:
            service.send_account_ready(
                "person@gmail.com",
                company_name="Acme Operations",
                login_email="employee@adverseindia.com",
                login_url="https://employee.adverseindia.com/login",
                password="StrongPass@123",
            )
        message = send.call_args.args[0]
        plain = message.get_body(preferencelist=("plain",)).get_content()
        html = message.get_body(preferencelist=("html",)).get_content()
        self.assertEqual(message["To"], "person@gmail.com")
        for body in (plain, html):
            self.assertIn("employee@adverseindia.com", body)
            self.assertIn("StrongPass@123", body)
            self.assertIn("https://employee.adverseindia.com/login", body)
        self.assertNotIn("expires in", html)  # a login does not expire like a setup link

    @patch.object(settings, "smtp_host", "mailpit")
    def test_welcome_email_without_password_shows_only_the_login(self) -> None:
        service = EmailService()
        with patch.object(service, "_send") as send:
            service.send_account_ready(
                "person@gmail.com",
                company_name="Acme Operations",
                login_email="employee@adverseindia.com",
                login_url="https://employee.adverseindia.com/login",
            )
        html = send.call_args.args[0].get_body(preferencelist=("html",)).get_content()
        self.assertIn("employee@adverseindia.com", html)
        self.assertNotIn(">Password<", html)


class MailDeliverySwitchTests(unittest.TestCase):
    def _message(self):
        from email.message import EmailMessage

        message = EmailMessage()
        message["Subject"] = "Hello"
        message["To"] = "client@gmail.com"
        message.set_content("Hi")
        return message

    @patch.object(settings, "mail_delivery_enabled", False)
    def test_no_mail_leaves_when_delivery_is_off(self) -> None:
        with patch("app.services.email_service.smtplib") as smtp:
            EmailService()._send(self._message())
        smtp.SMTP.assert_not_called()
        smtp.SMTP_SSL.assert_not_called()

    @patch.object(settings, "mail_delivery_enabled", False)
    @patch.object(settings, "smtp_host", "127.0.0.1")
    def test_health_is_ready_when_delivery_is_off(self) -> None:
        with patch("app.services.email_service.smtplib") as smtp:
            self.assertTrue(EmailService().is_ready())
        smtp.SMTP.assert_not_called()

    @patch.object(settings, "mail_delivery_enabled", True)
    @patch.object(settings, "mail_repeat_window_minutes", 0)
    @patch.object(settings, "smtp_username", "sender@gmail.com")
    def test_mail_is_sent_when_delivery_is_on(self) -> None:
        with patch("app.services.email_service.smtplib") as smtp:
            EmailService()._send(self._message())
        smtp.SMTP.assert_called_once()


if __name__ == "__main__":
    unittest.main()
