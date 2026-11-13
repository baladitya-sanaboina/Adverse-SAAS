from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from app.database.connectivity import database_pool


@dataclass(frozen=True)
class IntegrationRecord:
    provider: str
    status: str
    enabled: bool
    configuration: dict[str, bool]
    connected_at: datetime | None
    updated_at: datetime


@dataclass(frozen=True)
class WorkflowRecord:
    task_notifications: bool
    project_updates: bool
    approval_flow: bool
    client_notifications: bool
    updated_at: datetime


class CompanyIntegrationsRepository:
    def list(self, company_id: UUID) -> tuple[IntegrationRecord, ...]:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """SELECT provider,status,enabled,configuration,connected_at,updated_at
                    FROM company_integrations WHERE company_id=%s ORDER BY provider""",
                    (company_id,),
                )
                return tuple(IntegrationRecord(*row) for row in cursor.fetchall())

    def get(self, company_id: UUID, provider: str) -> IntegrationRecord | None:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """SELECT provider,status,enabled,configuration,connected_at,updated_at
                    FROM company_integrations WHERE company_id=%s AND provider=%s""",
                    (company_id, provider),
                )
                row = cursor.fetchone()
                return IntegrationRecord(*row) if row else None

    def upsert(
        self,
        actor_id: UUID,
        company_id: UUID,
        provider: str,
        enabled: bool,
        configuration: dict[str, bool],
    ) -> IntegrationRecord:
        status = "CONFIGURED" if enabled else "DISCONNECTED"
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO company_integrations
                    (id,company_id,provider,status,enabled,configuration,updated_by,created_at,updated_at)
                    VALUES(%s,%s,%s,%s,%s,%s,%s,NOW(),NOW())
                    ON CONFLICT(company_id,provider) DO UPDATE SET
                    status=EXCLUDED.status,enabled=EXCLUDED.enabled,
                    configuration=EXCLUDED.configuration,updated_by=EXCLUDED.updated_by,updated_at=NOW()""",
                    (
                        uuid4(),
                        company_id,
                        provider,
                        status,
                        enabled,
                        Jsonb(configuration),
                        actor_id,
                    ),
                )
                self._audit(
                    cursor,
                    actor_id,
                    company_id,
                    "INTEGRATION_CONFIG_UPDATED",
                    {"provider": provider},
                )
                self._audit(
                    cursor,
                    actor_id,
                    company_id,
                    "INTEGRATION_ENABLED" if enabled else "INTEGRATION_DISABLED",
                    {"provider": provider},
                )
        record = self.get(company_id, provider)
        assert record is not None
        return record

    def disconnect(
        self, actor_id: UUID, company_id: UUID, provider: str
    ) -> IntegrationRecord | None:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """UPDATE company_integrations SET status='DISCONNECTED',enabled=FALSE,
                    connected_at=NULL,updated_by=%s,updated_at=NOW()
                    WHERE company_id=%s AND provider=%s""",
                    (actor_id, company_id, provider),
                )
                if cursor.rowcount:
                    self._audit(
                        cursor,
                        actor_id,
                        company_id,
                        "INTEGRATION_DISCONNECTED",
                        {"provider": provider},
                    )
        return self.get(company_id, provider)

    def workflow(self, company_id: UUID) -> WorkflowRecord | None:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """SELECT task_notifications,project_updates,approval_flow,
                    client_notifications,updated_at FROM company_workflow_settings WHERE company_id=%s""",
                    (company_id,),
                )
                row = cursor.fetchone()
                return WorkflowRecord(*row) if row else None

    def update_workflow(
        self, actor_id: UUID, company_id: UUID, values: dict[str, bool]
    ) -> WorkflowRecord:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO company_workflow_settings
                    (company_id,task_notifications,project_updates,approval_flow,
                    client_notifications,updated_by,created_at,updated_at)
                    VALUES(%s,%s,%s,%s,%s,%s,NOW(),NOW())
                    ON CONFLICT(company_id) DO UPDATE SET
                    task_notifications=EXCLUDED.task_notifications,
                    project_updates=EXCLUDED.project_updates,
                    approval_flow=EXCLUDED.approval_flow,
                    client_notifications=EXCLUDED.client_notifications,
                    updated_by=EXCLUDED.updated_by,updated_at=NOW()""",
                    (
                        company_id,
                        values["task_notifications"],
                        values["project_updates"],
                        values["approval_flow"],
                        values["client_notifications"],
                        actor_id,
                    ),
                )
                self._audit(cursor, actor_id, company_id, "WORKFLOW_SETTING_UPDATED", values)
        record = self.workflow(company_id)
        assert record is not None
        return record

    @staticmethod
    def _audit(
        cursor: Any, actor_id: UUID, company_id: UUID, action: str, details: dict[str, Any]
    ) -> None:
        cursor.execute(
            """INSERT INTO company_setting_audits(id,actor_id,company_id,action,details)
            VALUES(%s,%s,%s,%s,%s)""",
            (uuid4(), actor_id, company_id, action, Jsonb(details)),
        )

    def is_ready(self) -> bool:
        try:
            with database_pool.connection(timeout=2) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """SELECT to_regclass('public.company_integrations') IS NOT NULL
                        AND to_regclass('public.company_workflow_settings') IS NOT NULL"""
                    )
                    row = cursor.fetchone()
                    return bool(row and row[0])
        except Exception:
            return False
