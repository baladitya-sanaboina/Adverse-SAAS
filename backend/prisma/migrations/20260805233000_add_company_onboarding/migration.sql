ALTER TABLE "companies"
  ADD COLUMN "phone" TEXT,
  ADD COLUMN "address" TEXT,
  ADD COLUMN "website" TEXT,
  ADD COLUMN "timezone" TEXT NOT NULL DEFAULT 'UTC',
  ADD COLUMN "language" TEXT NOT NULL DEFAULT 'en';

CREATE TABLE "company_onboardings" (
  "id" UUID NOT NULL,
  "company_id" UUID NOT NULL,
  "actor_id" UUID NOT NULL,
  "admin_user_id" UUID NOT NULL,
  "status" TEXT NOT NULL DEFAULT 'IN_PROGRESS',
  "company_created" BOOLEAN NOT NULL DEFAULT false,
  "subscription_assigned" BOOLEAN NOT NULL DEFAULT false,
  "admin_created" BOOLEAN NOT NULL DEFAULT false,
  "tenant_initialized" BOOLEAN NOT NULL DEFAULT false,
  "defaults_seeded" BOOLEAN NOT NULL DEFAULT false,
  "welcome_email_status" TEXT NOT NULL DEFAULT 'PENDING',
  "started_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "completed_at" TIMESTAMP(3),
  "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "company_onboardings_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "company_onboardings_company_id_key" ON "company_onboardings"("company_id");
CREATE INDEX "company_onboardings_actor_id_started_at_idx" ON "company_onboardings"("actor_id", "started_at");

CREATE TABLE "company_tenant_defaults" (
  "company_id" UUID NOT NULL,
  "logo_url" TEXT,
  "favicon_url" TEXT,
  "primary_color" TEXT NOT NULL,
  "secondary_color" TEXT NOT NULL,
  "theme" TEXT NOT NULL DEFAULT 'system',
  "timezone" TEXT NOT NULL,
  "language" TEXT NOT NULL,
  "default_roles" JSONB NOT NULL,
  "default_permissions" JSONB NOT NULL,
  "notification_preferences" JSONB NOT NULL,
  "dashboard_configuration" JSONB NOT NULL,
  "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "company_tenant_defaults_pkey" PRIMARY KEY ("company_id")
);

CREATE TABLE "company_onboarding_audits" (
  "id" UUID NOT NULL,
  "actor_id" UUID NOT NULL,
  "company_id" UUID,
  "action" TEXT NOT NULL,
  "details" JSONB,
  "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "company_onboarding_audits_pkey" PRIMARY KEY ("id")
);

CREATE INDEX "company_onboarding_audits_actor_id_created_at_idx" ON "company_onboarding_audits"("actor_id", "created_at");
CREATE INDEX "company_onboarding_audits_company_id_created_at_idx" ON "company_onboarding_audits"("company_id", "created_at");

ALTER TABLE "company_onboardings" ADD CONSTRAINT "company_onboardings_company_id_fkey" FOREIGN KEY ("company_id") REFERENCES "companies"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "company_onboardings" ADD CONSTRAINT "company_onboardings_actor_id_fkey" FOREIGN KEY ("actor_id") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
ALTER TABLE "company_tenant_defaults" ADD CONSTRAINT "company_tenant_defaults_company_id_fkey" FOREIGN KEY ("company_id") REFERENCES "companies"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "company_onboarding_audits" ADD CONSTRAINT "company_onboarding_audits_actor_id_fkey" FOREIGN KEY ("actor_id") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
ALTER TABLE "company_onboarding_audits" ADD CONSTRAINT "company_onboarding_audits_company_id_fkey" FOREIGN KEY ("company_id") REFERENCES "companies"("id") ON DELETE SET NULL ON UPDATE CASCADE;
