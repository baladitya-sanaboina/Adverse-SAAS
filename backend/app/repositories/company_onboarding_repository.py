import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from psycopg.errors import UniqueViolation

from app.database.connectivity import database_pool
from app.repositories.service_pricing_repository import seed_default_services


@dataclass(frozen=True)
class OnboardingRecord:
    id: UUID
    status: str
    company: dict[str, Any]
    subscription: dict[str, Any]
    admin: dict[str, Any]
    initialization: dict[str, Any]
    started_at: datetime
    completed_at: datetime | None
    audit_trail: list[dict[str, Any]]


class OnboardingConflict(Exception):
    def __init__(self, constraint: str | None):
        self.constraint = constraint


class CompanyOnboardingRepository:
    def actor_role(self, actor_id: UUID) -> str | None:
        with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT r.code FROM users u JOIN roles r ON r.id=u.role_id "
                "WHERE u.id=%s AND u.status='ACTIVE'",
                (actor_id,),
            )
            row = cursor.fetchone()
            return str(row[0]) if row else None

    def create(self, *, actor_id: UUID, payload: dict[str, Any], password_hash: str) -> UUID:
        company = payload["company"]
        admin = payload["admin"]
        plan_id = payload["subscription_plan_id"]
        onboarding_id, company_id, admin_id = uuid4(), uuid4(), uuid4()
        try:
            with database_pool.connection(timeout=3) as connection, connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id,name,code FROM subscription_plans WHERE id=%s AND status='ACTIVE'",
                    (plan_id,),
                )
                plan = cursor.fetchone()
                if not plan:
                    raise LookupError("PLAN_NOT_FOUND")
                cursor.execute("SELECT id FROM roles WHERE code='COMPANY_ADMIN'")
                role = cursor.fetchone()
                if not role:
                    raise RuntimeError("COMPANY_ADMIN role is not initialized.")
                cursor.execute(
                    "SELECT platform_logo_url,favicon_url,primary_color,secondary_color,"
                    "default_timezone,default_language FROM platform_settings WHERE id='global'"
                )
                defaults = cursor.fetchone() or (None, None, "#0876ED", "#065EC1", "UTC", "en")
                timezone = company["timezone"] or defaults[4]
                language = company["language"] or defaults[5]
                cursor.execute(
                    "INSERT INTO companies (id,name,code,subscription_plan,status,contact_email,phone,address,website,timezone,language,created_at,updated_at) "
                    "VALUES (%s,%s,%s,%s,'PENDING',%s,%s,%s,%s,%s,%s,NOW(),NOW())",
                    (
                        company_id,
                        company["name"],
                        company["code"],
                        plan[1],
                        company["business_email"],
                        company["phone"],
                        company["address"],
                        company["website"],
                        timezone,
                        language,
                    ),
                )
                self._audit(
                    cursor,
                    actor_id,
                    company_id,
                    "ONBOARDING_STARTED",
                    {"company_code": company["code"]},
                )
                self._audit(cursor, actor_id, company_id, "COMPANY_CREATED", None)
                cursor.execute(
                    "INSERT INTO company_subscriptions (id,company_id,plan_id,status,activation_date,created_at,updated_at) "
                    "VALUES (%s,%s,%s,'ACTIVE',NOW(),NOW(),NOW())",
                    (uuid4(), company_id, plan_id),
                )
                cursor.execute(
                    "INSERT INTO company_usage_metrics (company_id,created_at,updated_at) VALUES (%s,NOW(),NOW())",
                    (company_id,),
                )
                self._audit(
                    cursor, actor_id, company_id, "SUBSCRIPTION_ASSIGNED", {"plan": plan[2]}
                )
                seed_default_services(cursor, company_id)
                name = f"{admin['first_name']} {admin['last_name']}".strip()
                cursor.execute(
                    "INSERT INTO users (id,name,email,password_hash,status,company_id,role_id,first_name,last_name,phone_number,timezone,language,created_at,updated_at) "
                    "VALUES (%s,%s,%s,%s,'PENDING_VERIFICATION',%s,%s,%s,%s,%s,%s,%s,NOW(),NOW())",
                    (
                        admin_id,
                        name,
                        admin["email"],
                        password_hash,
                        company_id,
                        role[0],
                        admin["first_name"],
                        admin["last_name"],
                        admin["phone"],
                        timezone,
                        language,
                    ),
                )
                self._audit(
                    cursor,
                    actor_id,
                    company_id,
                    "COMPANY_ADMIN_CREATED",
                    {"admin_email": admin["email"]},
                )
                default_roles = [
                    "COMPANY_ADMIN",
                    "COMPANY_MANAGER",
                    "COMPANY_EMPLOYEE",
                    "COMPANY_CLIENT",
                ]
                cursor.execute(
                    "SELECT r.code,m.code,p.code FROM role_permissions rp "
                    "JOIN roles r ON r.id=rp.role_id JOIN modules m ON m.id=rp.module_id "
                    "JOIN permissions p ON p.id=rp.permission_id "
                    "WHERE r.code=ANY(%s) ORDER BY r.code,m.code,p.code",
                    (default_roles,),
                )
                default_permissions: dict[str, list[str]] = {
                    role_code: [] for role_code in default_roles
                }
                for role_code, module_code, permission_code in cursor.fetchall():
                    default_permissions[str(role_code)].append(f"{module_code}_{permission_code}")
                cursor.execute(
                    "INSERT INTO company_tenant_defaults (company_id,logo_url,favicon_url,primary_color,secondary_color,accent_color,theme,timezone,language,default_roles,default_permissions,notification_preferences,dashboard_configuration,created_at,updated_at) "
                    "VALUES (%s,%s,%s,%s,%s,%s,'system',%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,NOW(),NOW())",
                    (
                        company_id,
                        defaults[0],
                        defaults[1],
                        defaults[2],
                        defaults[3],
                        defaults[2],
                        timezone,
                        language,
                        json.dumps(default_roles),
                        json.dumps(default_permissions),
                        json.dumps({"email": True, "in_app": True}),
                        json.dumps({"layout": "default", "widgets": []}),
                    ),
                )
                cursor.execute(
                    "INSERT INTO company_onboardings (id,company_id,actor_id,admin_user_id,status,company_created,subscription_assigned,admin_created,tenant_initialized,defaults_seeded,welcome_email_status,started_at,updated_at) "
                    "VALUES (%s,%s,%s,%s,'EMAIL_PENDING',true,true,true,true,true,'PENDING',NOW(),NOW())",
                    (onboarding_id, company_id, actor_id, admin_id),
                )
                cursor.execute(
                    "UPDATE companies SET status='ACTIVE',updated_at=NOW() WHERE id=%s",
                    (company_id,),
                )
            return company_id
        except UniqueViolation as error:
            raise OnboardingConflict(error.diag.constraint_name) from error

    @staticmethod
    def _audit(
        cursor: Any,
        actor_id: UUID,
        company_id: UUID | None,
        action: str,
        details: dict[str, Any] | None,
    ) -> None:
        cursor.execute(
            "INSERT INTO company_onboarding_audits (id,actor_id,company_id,action,details,created_at) VALUES (%s,%s,%s,%s,%s::jsonb,NOW())",
            (uuid4(), actor_id, company_id, action, json.dumps(details) if details else None),
        )

    def finish_email(self, company_id: UUID, actor_id: UUID, sent: bool) -> None:
        with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
            status = "COMPLETED" if sent else "EMAIL_FAILED"
            email_status = "SENT" if sent else "FAILED"
            cursor.execute(
                "UPDATE company_onboardings SET status=%s,welcome_email_status=%s,completed_at=CASE WHEN %s THEN NOW() ELSE NULL END,updated_at=NOW() WHERE company_id=%s",
                (status, email_status, sent, company_id),
            )
            self._audit(
                cursor,
                actor_id,
                company_id,
                "WELCOME_EMAIL_SENT" if sent else "WELCOME_EMAIL_FAILED",
                None,
            )
            if sent:
                self._audit(cursor, actor_id, company_id, "ONBOARDING_COMPLETED", None)

    def get(self, company_id: UUID) -> OnboardingRecord | None:
        with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT o.id,o.status,o.started_at,o.completed_at,o.company_created,o.subscription_assigned,o.admin_created,o.tenant_initialized,o.defaults_seeded,o.welcome_email_status,"
                "c.id,c.name,c.code,c.contact_email,c.phone,c.address,c.website,c.timezone,c.language,c.status::text,"
                "p.id,p.name,p.code,COALESCE(f.items,'{}'::jsonb),COALESCE(l.items,'{}'::jsonb),"
                "u.id,u.name,u.email,u.phone_number,r.code,u.status::text "
                "FROM company_onboardings o JOIN companies c ON c.id=o.company_id "
                "JOIN company_subscriptions cs ON cs.company_id=c.id JOIN subscription_plans p ON p.id=cs.plan_id "
                "LEFT JOIN LATERAL (SELECT jsonb_object_agg(feature_code,enabled) items FROM subscription_plan_features WHERE plan_id=p.id) f ON TRUE "
                "LEFT JOIN LATERAL (SELECT jsonb_object_agg(limit_code,value) items FROM subscription_plan_limits WHERE plan_id=p.id) l ON TRUE "
                "JOIN users u ON u.id=o.admin_user_id JOIN roles r ON r.id=u.role_id WHERE c.id=%s",
                (company_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            cursor.execute(
                "SELECT action,created_at,details FROM company_onboarding_audits WHERE company_id=%s ORDER BY created_at",
                (company_id,),
            )
            audits = [
                {"action": a[0], "created_at": a[1], "details": a[2]} for a in cursor.fetchall()
            ]
            return OnboardingRecord(
                id=row[0],
                status=row[1],
                started_at=row[2],
                completed_at=row[3],
                initialization={
                    "company_created": row[4],
                    "subscription_assigned": row[5],
                    "admin_created": row[6],
                    "tenant_initialized": row[7],
                    "defaults_seeded": row[8],
                    "welcome_email": row[9],
                },
                company={
                    "id": row[10],
                    "name": row[11],
                    "code": row[12],
                    "business_email": row[13],
                    "phone": row[14],
                    "address": row[15],
                    "website": row[16],
                    "timezone": row[17],
                    "language": row[18],
                    "status": row[19],
                },
                subscription={
                    "id": row[20],
                    "name": row[21],
                    "code": row[22],
                    "features": dict(row[23]),
                    "limits": {
                        k: int(v) if v is not None else None for k, v in dict(row[24]).items()
                    },
                },
                admin={
                    "id": row[25],
                    "name": row[26],
                    "email": row[27],
                    "phone": row[28],
                    "role": row[29],
                    "status": row[30],
                },
                audit_trail=audits,
            )

    def is_ready(self) -> bool:
        try:
            with database_pool.connection(timeout=2) as connection, connection.cursor() as cursor:
                cursor.execute("SELECT to_regclass('public.company_onboardings') IS NOT NULL")
                row = cursor.fetchone()
                return bool(row and row[0])
        except Exception:
            return False
