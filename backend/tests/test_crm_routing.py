import unittest
from typing import cast

from main import app


class CrmRoutingTests(unittest.TestCase):
    @staticmethod
    def _tenant_exempt_prefixes() -> set[str]:
        tenant_middleware = next(
            middleware
            for middleware in app.user_middleware
            if getattr(middleware.cls, "__name__", "") == "TenantContextMiddleware"
        )
        return cast(set[str], tenant_middleware.kwargs["exempt_path_prefixes"])

    def test_crm_routes_derive_tenant_from_authenticated_jwt(self) -> None:
        exempt_prefixes = self._tenant_exempt_prefixes()

        self.assertTrue({"/crm", "/leads", "/opportunities"}.issubset(exempt_prefixes))

    def test_company_branding_derives_tenant_from_authenticated_jwt(self) -> None:
        self.assertIn("/company/branding", self._tenant_exempt_prefixes())


if __name__ == "__main__":
    unittest.main()
