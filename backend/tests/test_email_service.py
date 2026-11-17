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
        self.assertIn("#0876ED", html)
        self.assertIn('name="color-scheme" content="light"', html)

    @patch.object(settings, "smtp_host", "mailpit")
    def test_verification_email_has_plain_and_branded_html_parts(self) -> None:
        service = EmailService()
        code = "482951"
        verification_url = "https://employee.adverseindia.com/verify-email?email=user%40example.com&otp=482951"
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
        self.assertIn("never included", html)
        self.assertNotIn("StrongPass", message.as_string())


if __name__ == "__main__":
    unittest.main()
