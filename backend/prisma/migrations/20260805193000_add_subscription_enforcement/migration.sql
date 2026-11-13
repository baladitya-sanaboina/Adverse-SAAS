CREATE TABLE "company_usage_metrics" (
    "company_id" UUID NOT NULL,
    "projects_used" BIGINT NOT NULL DEFAULT 0,
    "storage_used_bytes" BIGINT NOT NULL DEFAULT 0,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "company_usage_metrics_pkey" PRIMARY KEY ("company_id")
);

CREATE TABLE "subscription_usage_alerts" (
    "id" UUID NOT NULL,
    "company_id" UUID NOT NULL,
    "resource_code" TEXT NOT NULL,
    "level" TEXT NOT NULL,
    "message" TEXT NOT NULL,
    "active" BOOLEAN NOT NULL DEFAULT true,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "subscription_usage_alerts_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "subscription_enforcement_audits" (
    "id" UUID NOT NULL,
    "company_id" UUID NOT NULL,
    "actor_id" UUID,
    "plan_id" UUID,
    "event_type" TEXT NOT NULL,
    "resource_code" TEXT,
    "current_usage" BIGINT,
    "configured_limit" BIGINT,
    "details" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "subscription_enforcement_audits_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "subscription_usage_alerts_company_id_resource_code_key"
ON "subscription_usage_alerts"("company_id", "resource_code");
CREATE INDEX "subscription_usage_alerts_company_id_active_idx"
ON "subscription_usage_alerts"("company_id", "active");
CREATE INDEX "subscription_enforcement_audits_company_id_created_at_idx"
ON "subscription_enforcement_audits"("company_id", "created_at");
CREATE INDEX "subscription_enforcement_audits_event_type_created_at_idx"
ON "subscription_enforcement_audits"("event_type", "created_at");

ALTER TABLE "company_usage_metrics" ADD CONSTRAINT "company_usage_metrics_company_id_fkey"
FOREIGN KEY ("company_id") REFERENCES "companies"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "subscription_usage_alerts" ADD CONSTRAINT "subscription_usage_alerts_company_id_fkey"
FOREIGN KEY ("company_id") REFERENCES "companies"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "subscription_enforcement_audits" ADD CONSTRAINT "subscription_enforcement_audits_company_id_fkey"
FOREIGN KEY ("company_id") REFERENCES "companies"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "subscription_enforcement_audits" ADD CONSTRAINT "subscription_enforcement_audits_actor_id_fkey"
FOREIGN KEY ("actor_id") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;
ALTER TABLE "subscription_enforcement_audits" ADD CONSTRAINT "subscription_enforcement_audits_plan_id_fkey"
FOREIGN KEY ("plan_id") REFERENCES "subscription_plans"("id") ON DELETE SET NULL ON UPDATE CASCADE;
