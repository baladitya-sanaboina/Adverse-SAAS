import unittest

from pydantic import ValidationError

from app.core.settings import Settings

BASE_CONFIGURATION = {
    "database_url": "postgresql://user:password@localhost:5432/loopless",
    "redis_url": "redis://localhost:6379/0",
    "jwt_secret": "a-secure-development-secret-with-32-characters",
}


class ConfigurationTests(unittest.TestCase):
    def test_configuration_loads_and_splits_cors_origins(self):
        configuration = Settings(
            **BASE_CONFIGURATION,
            cors_origins="http://localhost:3000, http://localhost:3001",
            _env_file=None,
        )
        self.assertEqual(configuration.app_name, "Adverse API")
        self.assertEqual(
            configuration.allowed_origins,
            ["http://localhost:3000", "http://localhost:3001"],
        )

    def test_required_connection_values_reject_empty_text(self):
        for field in ("database_url", "redis_url"):
            with (
                self.subTest(field=field),
                self.assertRaisesRegex(ValidationError, "must not be empty"),
            ):
                Settings(
                    **{**BASE_CONFIGURATION, field: ""},
                    _env_file=None,
                )

    def test_short_jwt_secret_is_rejected(self):
        with self.assertRaisesRegex(ValidationError, "at least 32"):
            Settings(
                **{**BASE_CONFIGURATION, "jwt_secret": "too-short"},
                _env_file=None,
            )

    def test_development_secret_is_rejected_in_production(self):
        with self.assertRaisesRegex(ValidationError, "must be replaced for production"):
            Settings(
                **{**BASE_CONFIGURATION, "environment": "production"},
                _env_file=None,
            )

    def test_api_docs_are_off_in_production(self):
        configuration = Settings(
            **{
                **BASE_CONFIGURATION,
                "environment": "production",
                "jwt_secret": "a-real-secret-value-that-is-long-enough-123",
                "smtp_host": "smtp.example.com",
                "smtp_from_email": "team@example.com",
                "swagger_enabled": True,
            },
            _env_file=None,
        )
        self.assertFalse(configuration.swagger_enabled)


if __name__ == "__main__":
    unittest.main()
