"""The company admin login from .env (owner request 2026-11-19).

DEFAULT_ADMIN_EMAIL (internal login, e.g. admin@adverseindia.com), DEFAULT_ADMIN_RECOVERY_EMAIL
(their Gmail: password resets go there) and DEFAULT_ADMIN_PASSWORD. On start:
- the login exists: its Gmail is kept in step with .env; nothing else changes;
- it does not exist and there is exactly one active company: it is created as that company's
  admin with the .env password. The password is used only here, so changing it later in the
  app sticks across restarts.
Never raises: a problem is logged and the app starts normally.
"""

from __future__ import annotations

import logging
from uuid import uuid4

from app.core.settings import settings
from app.database.connectivity import database_pool
from app.services.password_service import hash_password

logger = logging.getLogger(__name__)


def ensure() -> None:
    login = settings.default_admin_email.strip().lower()
    if not login:
        return
    gmail = settings.default_admin_recovery_email.strip().lower() or None
    password = settings.default_admin_password.get_secret_value()
    try:
        with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute(
                'SELECT u.id, r.code FROM "users" u JOIN roles r ON r.id = u.role_id '
                "WHERE LOWER(u.email) = %s",
                (login,),
            )
            found = cursor.fetchone()
            if found:
                if gmail:
                    cursor.execute(
                        'UPDATE "users" SET recovery_email = %s, updated_at = NOW() '
                        "WHERE id = %s AND recovery_email IS DISTINCT FROM %s",
                        (gmail, found[0], gmail),
                    )
                if found[1] != "COMPANY_ADMIN":
                    logger.warning("DEFAULT_ADMIN_EMAIL %s is not a company admin login.", login)
                return
            if not password:
                logger.warning("DEFAULT_ADMIN_PASSWORD is empty; the admin %s was not made.", login)
                return
            cursor.execute(
                "SELECT id, COALESCE(NULLIF(timezone, ''), 'UTC'), COALESCE(NULLIF(language, ''), 'en') "
                "FROM companies WHERE status = 'ACTIVE' ORDER BY created_at"
            )
            companies = cursor.fetchall()
            if len(companies) != 1:
                logger.warning(
                    "The admin %s was not made: %d active companies (needs exactly one).",
                    login,
                    len(companies),
                )
                return
            company_id, timezone, language = companies[0]
            cursor.execute("SELECT id FROM roles WHERE code = 'COMPANY_ADMIN'")
            role = cursor.fetchone()
            if role is None:
                logger.warning(
                    "The COMPANY_ADMIN role is missing; the admin %s was not made.", login
                )
                return
            name = settings.default_admin_name.strip() or "Admin"
            first, _, last = name.partition(" ")
            cursor.execute(
                'INSERT INTO "users" (id, name, email, password_hash, status, company_id, role_id, '
                "first_name, last_name, timezone, language, recovery_email, failed_login_attempts, "
                "created_at, updated_at) VALUES (%s, %s, %s, %s, 'ACTIVE', %s, %s, %s, %s, %s, %s, "
                "%s, 0, NOW(), NOW())",
                (
                    uuid4(),
                    name,
                    login,
                    hash_password(password),
                    company_id,
                    role[0],
                    first,
                    last or None,
                    timezone,
                    language,
                    gmail,
                ),
            )
            logger.info("Default admin login %s created.", login)
    except Exception:  # noqa: BLE001 - never stop the app from starting
        logger.warning("Default admin setup failed", exc_info=True)
