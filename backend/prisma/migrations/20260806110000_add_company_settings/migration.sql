ALTER TABLE "company_tenant_defaults"
  ADD COLUMN "email_footer" TEXT NOT NULL DEFAULT '',
  ADD COLUMN "support_email" TEXT,
  ADD COLUMN "support_phone" TEXT,
  ADD COLUMN "gst_tax_id" TEXT,
  ADD COLUMN "registration_number" TEXT,
  ADD COLUMN "currency" TEXT NOT NULL DEFAULT 'USD',
  ADD COLUMN "date_format" TEXT NOT NULL DEFAULT 'DD/MM/YYYY',
  ADD COLUMN "time_format" TEXT NOT NULL DEFAULT '12_HOUR',
  ADD COLUMN "working_days" TEXT[] NOT NULL DEFAULT ARRAY['MONDAY','TUESDAY','WEDNESDAY','THURSDAY','FRIDAY']::TEXT[],
  ADD COLUMN "business_hours" JSONB NOT NULL DEFAULT '{"start":"09:00","end":"18:00"}'::JSONB;

INSERT INTO "company_tenant_defaults" (
  "company_id", "primary_color", "secondary_color", "theme", "timezone", "language",
  "default_roles", "default_permissions", "notification_preferences", "dashboard_configuration"
)
SELECT c."id", p."primary_color", p."secondary_color", 'system', c."timezone", c."language",
  '[]'::JSONB, '[]'::JSONB,
  '{"email":true,"system":true,"maintenance":true,"security":true}'::JSONB,
  '{}'::JSONB
FROM "companies" c CROSS JOIN "platform_settings" p
WHERE p."id" = 'global'
ON CONFLICT ("company_id") DO NOTHING;

CREATE TABLE "company_setting_audits" (
  "id" UUID NOT NULL,
  "actor_id" UUID NOT NULL,
  "company_id" UUID NOT NULL,
  "action" TEXT NOT NULL,
  "details" JSONB,
  "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "company_setting_audits_pkey" PRIMARY KEY ("id")
);
CREATE INDEX "company_setting_audits_actor_id_created_at_idx" ON "company_setting_audits"("actor_id", "created_at");
CREATE INDEX "company_setting_audits_company_id_created_at_idx" ON "company_setting_audits"("company_id", "created_at");
ALTER TABLE "company_setting_audits" ADD CONSTRAINT "company_setting_audits_actor_id_fkey" FOREIGN KEY ("actor_id") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
ALTER TABLE "company_setting_audits" ADD CONSTRAINT "company_setting_audits_company_id_fkey" FOREIGN KEY ("company_id") REFERENCES "companies"("id") ON DELETE CASCADE ON UPDATE CASCADE;
