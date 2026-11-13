CREATE TYPE "CompanyIntegrationProvider" AS ENUM ('GOOGLE_DRIVE', 'SLACK', 'STRIPE');
CREATE TYPE "CompanyIntegrationStatus" AS ENUM ('NOT_CONFIGURED', 'CONFIGURED', 'CONNECTED', 'DISCONNECTED', 'ERROR');

CREATE TABLE "company_integrations" (
  "id" UUID NOT NULL,
  "company_id" UUID NOT NULL,
  "provider" "CompanyIntegrationProvider" NOT NULL,
  "status" "CompanyIntegrationStatus" NOT NULL DEFAULT 'NOT_CONFIGURED',
  "enabled" BOOLEAN NOT NULL DEFAULT FALSE,
  "configuration" JSONB NOT NULL DEFAULT '{}',
  "connected_at" TIMESTAMPTZ,
  "updated_by" UUID NOT NULL,
  "created_at" TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  "updated_at" TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT "company_integrations_pkey" PRIMARY KEY ("id"),
  CONSTRAINT "company_integrations_company_provider_key" UNIQUE ("company_id", "provider"),
  CONSTRAINT "company_integrations_company_fkey" FOREIGN KEY ("company_id") REFERENCES "companies"("id") ON DELETE CASCADE,
  CONSTRAINT "company_integrations_updated_by_fkey" FOREIGN KEY ("updated_by") REFERENCES "users"("id") ON DELETE RESTRICT
);

CREATE INDEX "company_integrations_company_status_idx" ON "company_integrations"("company_id", "status");

CREATE TABLE "company_workflow_settings" (
  "company_id" UUID NOT NULL,
  "task_notifications" BOOLEAN NOT NULL DEFAULT TRUE,
  "project_updates" BOOLEAN NOT NULL DEFAULT TRUE,
  "approval_flow" BOOLEAN NOT NULL DEFAULT FALSE,
  "client_notifications" BOOLEAN NOT NULL DEFAULT TRUE,
  "updated_by" UUID NOT NULL,
  "created_at" TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  "updated_at" TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT "company_workflow_settings_pkey" PRIMARY KEY ("company_id"),
  CONSTRAINT "company_workflow_settings_company_fkey" FOREIGN KEY ("company_id") REFERENCES "companies"("id") ON DELETE CASCADE,
  CONSTRAINT "company_workflow_settings_updated_by_fkey" FOREIGN KEY ("updated_by") REFERENCES "users"("id") ON DELETE RESTRICT
);
