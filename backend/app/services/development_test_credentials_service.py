import json
import logging
from dataclasses import dataclass
from uuid import UUID, uuid4

from app.core.settings import settings
from app.database.connectivity import database_pool
from app.repositories.service_pricing_repository import seed_default_services
from app.services.password_service import hash_password

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DevelopmentTestAccount:
    email: str
    role_code: str
    name: str
    first_name: str
    last_name: str


_TEST_PASSWORD = "1234"
_TEST_COMPANY_NAME = "Adverse Test Workspace"
_TEST_COMPANY_CODE = "ADVERSETEST"
_TEAM_ROLE_CODE_PREFIXES = {
    "COMPANY_MANAGER": "MGR",
    "COMPANY_EMPLOYEE": "EMP",
}
_CLIENT_ROLE_CODE = "COMPANY_CLIENT"
_TEST_ACCOUNTS: tuple[DevelopmentTestAccount, ...] = (
    DevelopmentTestAccount(
        email="adverseadmin@gmail.com",
        role_code="COMPANY_ADMIN",
        name="Adverse Admin",
        first_name="Adverse",
        last_name="Admin",
    ),
    DevelopmentTestAccount(
        email="adversemanager@gmail.com",
        role_code="COMPANY_MANAGER",
        name="Adverse Manager",
        first_name="Adverse",
        last_name="Manager",
    ),
    DevelopmentTestAccount(
        email="adverseemployee@gmail.com",
        role_code="COMPANY_EMPLOYEE",
        name="Adverse Employee",
        first_name="Adverse",
        last_name="Employee",
    ),
    DevelopmentTestAccount(
        email="adverseclient@gmail.com",
        role_code="COMPANY_CLIENT",
        name="Adverse Client",
        first_name="Adverse",
        last_name="Client",
    ),
)


class DevelopmentTestCredentialsService:
    def ensure(self) -> None:
        if settings.environment == "production":
            return

        try:
            with database_pool.connection(timeout=2) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT to_regclass('public.users') IS NOT NULL "
                        "AND to_regclass('public.roles') IS NOT NULL "
                        "AND to_regclass('public.companies') IS NOT NULL "
                        "AND to_regclass('public.company_tenant_defaults') IS NOT NULL "
                        "AND to_regclass('public.subscription_plans') IS NOT NULL"
                    )
                    ready = cursor.fetchone()
                    if not ready or not ready[0]:
                        logger.info("Skipping development test credentials bootstrap; auth tables are not ready.")
                        return

                    role_ids = self._role_ids(cursor)
                    if len(role_ids) != len(_TEST_ACCOUNTS):
                        missing = sorted(
                            account.role_code
                            for account in _TEST_ACCOUNTS
                            if account.role_code not in role_ids
                        )
                        logger.warning(
                            "Skipping development test credentials bootstrap; missing roles: %s",
                            ", ".join(missing),
                        )
                        return

                    company_id, timezone, language = self._resolve_company(cursor)
                    password_hash = hash_password(_TEST_PASSWORD)
                    for account in _TEST_ACCOUNTS:
                        self._upsert_account(
                            cursor,
                            company_id=company_id,
                            role_id=role_ids[account.role_code],
                            timezone=timezone,
                            language=language,
                            account=account,
                            password_hash=password_hash,
                        )
            logger.info("Development test credentials ensured for Admin, Manager, Employee, and Client.")
        except Exception as error:
            logger.warning("Failed to ensure development test credentials: %s", error)

    @staticmethod
    def _role_ids(cursor) -> dict[str, UUID]:
        cursor.execute(
            "SELECT code, id FROM roles WHERE code = ANY(%s)",
            ([account.role_code for account in _TEST_ACCOUNTS],),
        )
        return {str(code): role_id for code, role_id in cursor.fetchall()}

    def _resolve_company(self, cursor) -> tuple[UUID, str, str]:
        cursor.execute(
            "SELECT c.id, COALESCE(NULLIF(c.timezone, ''), 'UTC'), "
            "COALESCE(NULLIF(c.language, ''), 'en') "
            "FROM companies c "
            "JOIN company_tenant_defaults d ON d.company_id = c.id "
            "JOIN users u ON u.company_id = c.id AND u.status = 'ACTIVE' "
            "JOIN roles r ON r.id = u.role_id AND r.code = 'COMPANY_ADMIN' "
            "WHERE c.status = 'ACTIVE' "
            "ORDER BY c.updated_at DESC, c.created_at DESC LIMIT 1"
        )
        company = cursor.fetchone()
        if company:
            company_id, timezone, language = company
            return company_id, str(timezone), str(language)
        return self._create_company(cursor)

    def _create_company(self, cursor) -> tuple[UUID, str, str]:
        cursor.execute(
            "SELECT id, name FROM subscription_plans WHERE code = 'STARTER' AND status = 'ACTIVE' LIMIT 1"
        )
        plan = cursor.fetchone()
        if not plan:
            cursor.execute(
                "SELECT id, name FROM subscription_plans WHERE status = 'ACTIVE' ORDER BY display_order, created_at LIMIT 1"
            )
            plan = cursor.fetchone()
        if not plan:
            raise RuntimeError("No active subscription plan is available for the test workspace.")

        plan_id, plan_name = plan
        company_id = uuid4()
        timezone = "Asia/Kolkata"
        language = "en"

        cursor.execute(
            "SELECT COALESCE(json_agg(code ORDER BY code), '[]'::json) FROM roles "
            "WHERE code IN ('COMPANY_ADMIN','COMPANY_MANAGER','COMPANY_EMPLOYEE','COMPANY_CLIENT')"
        )
        default_roles = cursor.fetchone()[0]
        cursor.execute(
            "SELECT r.code, m.code, p.code FROM role_permissions rp "
            "JOIN roles r ON r.id = rp.role_id "
            "JOIN modules m ON m.id = rp.module_id "
            "JOIN permissions p ON p.id = rp.permission_id "
            "WHERE r.code IN ('COMPANY_ADMIN','COMPANY_MANAGER','COMPANY_EMPLOYEE','COMPANY_CLIENT') "
            "ORDER BY r.code, m.code, p.code"
        )
        default_permissions: dict[str, list[str]] = {
            "COMPANY_ADMIN": [],
            "COMPANY_MANAGER": [],
            "COMPANY_EMPLOYEE": [],
            "COMPANY_CLIENT": [],
        }
        for role_code, module_code, permission_code in cursor.fetchall():
            default_permissions[str(role_code)].append(f"{module_code}_{permission_code}")

        cursor.execute(
            "INSERT INTO companies (id, name, code, subscription_plan, status, contact_email, timezone, language, created_at, updated_at) "
            "VALUES (%s, %s, %s, %s, 'ACTIVE', %s, %s, %s, NOW(), NOW())",
            (
                company_id,
                _TEST_COMPANY_NAME,
                _TEST_COMPANY_CODE,
                str(plan_name),
                _TEST_ACCOUNTS[0].email,
                timezone,
                language,
            ),
        )
        cursor.execute(
            "INSERT INTO company_subscriptions (id, company_id, plan_id, status, activation_date, created_at, updated_at) "
            "VALUES (%s, %s, %s, 'ACTIVE', NOW(), NOW(), NOW())",
            (uuid4(), company_id, plan_id),
        )
        cursor.execute(
            "INSERT INTO company_usage_metrics (company_id, created_at, updated_at) VALUES (%s, NOW(), NOW())",
            (company_id,),
        )
        cursor.execute(
            "INSERT INTO company_tenant_defaults (company_id, primary_color, secondary_color, accent_color, theme, timezone, language, default_roles, default_permissions, notification_preferences, dashboard_configuration, email_footer, currency, date_format, time_format, business_hours, created_at, updated_at) "
            "VALUES (%s, '#0876ED', '#065EC1', '#0876ED', 'system', %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, '', 'USD', 'DD/MM/YYYY', '12_HOUR', %s::jsonb, NOW(), NOW())",
            (
                company_id,
                timezone,
                language,
                json.dumps(default_roles),
                json.dumps(default_permissions),
                json.dumps({"email": True, "in_app": True}),
                json.dumps({"layout": "default", "widgets": []}),
                json.dumps({"start": "09:00", "end": "18:00"}),
            ),
        )
        seed_default_services(cursor, company_id)
        logger.info("Created fallback Adverse test workspace for development logins.")
        return company_id, timezone, language

    @staticmethod
    def _upsert_account(
        cursor,
        *,
        company_id: UUID,
        role_id: UUID,
        timezone: str,
        language: str,
        account: DevelopmentTestAccount,
        password_hash: str,
    ) -> None:
        cursor.execute(
            'SELECT id FROM "users" WHERE LOWER(email) = LOWER(%s) LIMIT 1',
            (account.email,),
        )
        user = cursor.fetchone()
        if user is None:
            cursor.execute(
                'SELECT u.id FROM "users" u JOIN roles r ON r.id = u.role_id '
                "WHERE u.company_id = %s AND r.code = %s "
                "ORDER BY CASE WHEN u.status = 'ACTIVE' THEN 0 ELSE 1 END, u.updated_at DESC, u.created_at DESC LIMIT 1",
                (company_id, account.role_code),
            )
            user = cursor.fetchone()

        if user is None:
            user_id = uuid4()
            cursor.execute(
                'INSERT INTO "users" '
                "(id, name, email, password_hash, status, company_id, role_id, first_name, last_name, timezone, language, failed_login_attempts, locked_until, created_at, updated_at) "
                "VALUES (%s, %s, %s, %s, 'ACTIVE', %s, %s, %s, %s, %s, %s, 0, NULL, NOW(), NOW())",
                (
                    user_id,
                    account.name,
                    account.email,
                    password_hash,
                    company_id,
                    role_id,
                    account.first_name,
                    account.last_name,
                    timezone,
                    language,
                ),
            )
            DevelopmentTestCredentialsService._sync_employee_profile(
                cursor,
                company_id=company_id,
                user_id=user_id,
                role_id=role_id,
                role_code=account.role_code,
            )
            DevelopmentTestCredentialsService._sync_client_profile(
                cursor,
                company_id=company_id,
                user_id=user_id,
                role_code=account.role_code,
                account=account,
            )
            return

        cursor.execute(
            'UPDATE "users" SET name = %s, email = %s, password_hash = %s, '
            "status = 'ACTIVE', company_id = %s, role_id = %s, first_name = %s, last_name = %s, "
            "timezone = %s, language = %s, failed_login_attempts = 0, locked_until = NULL, updated_at = NOW() "
            "WHERE id = %s",
            (
                account.name,
                account.email,
                password_hash,
                company_id,
                role_id,
                account.first_name,
                account.last_name,
                timezone,
                language,
                user[0],
            ),
        )
        DevelopmentTestCredentialsService._sync_employee_profile(
            cursor,
            company_id=company_id,
            user_id=user[0],
            role_id=role_id,
            role_code=account.role_code,
        )
        DevelopmentTestCredentialsService._sync_client_profile(
            cursor,
            company_id=company_id,
            user_id=user[0],
            role_code=account.role_code,
            account=account,
        )

    @staticmethod
    def _sync_employee_profile(
        cursor,
        *,
        company_id: UUID,
        user_id: UUID,
        role_id: UUID,
        role_code: str,
    ) -> None:
        employee_code_prefix = _TEAM_ROLE_CODE_PREFIXES.get(role_code)
        if employee_code_prefix is None:
            cursor.execute(
                "DELETE FROM employees WHERE user_id=%s",
                (user_id,),
            )
            return

        cursor.execute(
            "SELECT id FROM employees WHERE user_id=%s LIMIT 1",
            (user_id,),
        )
        employee = cursor.fetchone()
        if employee is None:
            cursor.execute(
                "INSERT INTO employees("
                "id,company_id,user_id,employee_code,department_id,branch_id,role_id,status,created_at,updated_at"
                ") VALUES(%s,%s,%s,%s,NULL,NULL,%s,'ACTIVE',NOW(),NOW())",
                (
                    uuid4(),
                    company_id,
                    user_id,
                    f"{employee_code_prefix}-{str(user_id).replace('-', '')[:8].upper()}",
                    role_id,
                ),
            )
            return

        cursor.execute(
            "UPDATE employees SET company_id=%s, role_id=%s, status='ACTIVE', updated_at=NOW() WHERE id=%s",
            (company_id, role_id, employee[0]),
        )

    @staticmethod
    def _sync_client_profile(
        cursor,
        *,
        company_id: UUID,
        user_id: UUID,
        role_code: str,
        account: DevelopmentTestAccount,
    ) -> None:
        if role_code != _CLIENT_ROLE_CODE:
            cursor.execute(
                "UPDATE clients SET user_id=NULL,updated_at=NOW() WHERE user_id=%s",
                (user_id,),
            )
            return

        cursor.execute(
            "SELECT id FROM clients WHERE user_id=%s LIMIT 1",
            (user_id,),
        )
        client = cursor.fetchone()
        if client is None:
            cursor.execute(
                "SELECT id FROM clients WHERE company_id=%s AND LOWER(email)=LOWER(%s) LIMIT 1",
                (company_id, account.email),
            )
            client = cursor.fetchone()

        if client is None:
            cursor.execute(
                "INSERT INTO clients("
                "id,company_id,user_id,name,code,email,address,city,state,country,status,created_at,updated_at"
                ") VALUES(%s,%s,%s,%s,%s,%s,'','','','India','ACTIVE',NOW(),NOW())",
                (
                    uuid4(),
                    company_id,
                    user_id,
                    account.name,
                    f"CLI-{str(user_id).replace('-', '')[:8].upper()}",
                    account.email,
                ),
            )
            return

        cursor.execute(
            "UPDATE clients SET company_id=%s,user_id=%s,name=%s,email=%s,status='ACTIVE',updated_at=NOW() WHERE id=%s",
            (company_id, user_id, account.name, account.email, client[0]),
        )


development_test_credentials_service = DevelopmentTestCredentialsService()
