CREATE TABLE "platform_settings" (
  "id" TEXT NOT NULL DEFAULT 'global',
  "platform_name" TEXT NOT NULL DEFAULT 'Adverse',
  "platform_logo_url" TEXT,
  "favicon_url" TEXT,
  "primary_color" TEXT NOT NULL DEFAULT '#0876ED',
  "secondary_color" TEXT NOT NULL DEFAULT '#065EC1',
  "footer_text" TEXT NOT NULL DEFAULT '© Adverse',
  "support_email" TEXT NOT NULL DEFAULT 'support@adverse.example.com',
  "support_phone" TEXT,
  "default_timezone" TEXT NOT NULL DEFAULT 'UTC',
  "default_language" TEXT NOT NULL DEFAULT 'en',
  "default_company_status" TEXT NOT NULL DEFAULT 'ACTIVE',
  "default_user_status" TEXT NOT NULL DEFAULT 'PENDING_VERIFICATION',
  "default_subscription_code" TEXT NOT NULL DEFAULT 'STARTER',
  "smtp_host" TEXT NOT NULL DEFAULT 'mailpit',
  "smtp_port" INTEGER NOT NULL DEFAULT 1025,
  "smtp_username" TEXT NOT NULL DEFAULT '',
  "smtp_password_encrypted" TEXT NOT NULL DEFAULT '',
  "smtp_encryption" TEXT NOT NULL DEFAULT 'NONE',
  "smtp_sender_name" TEXT NOT NULL DEFAULT 'Adverse',
  "smtp_sender_email" TEXT NOT NULL DEFAULT 'no-reply@adverse.example.com',
  "maintenance_enabled" BOOLEAN NOT NULL DEFAULT FALSE,
  "maintenance_message" TEXT NOT NULL DEFAULT 'Adverse is temporarily unavailable while scheduled maintenance is in progress.',
  "maintenance_allowed_roles" TEXT[] NOT NULL DEFAULT ARRAY['PLATFORM_OWNER']::TEXT[],
  "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "platform_settings_pkey" PRIMARY KEY ("id"),
  CONSTRAINT "platform_settings_singleton" CHECK ("id" = 'global'),
  CONSTRAINT "platform_settings_smtp_port" CHECK ("smtp_port" > 0 AND "smtp_port" <= 65535),
  CONSTRAINT "platform_settings_primary_color" CHECK ("primary_color" ~ '^#[0-9A-Fa-f]{6}$'),
  CONSTRAINT "platform_settings_secondary_color" CHECK ("secondary_color" ~ '^#[0-9A-Fa-f]{6}$')
);

CREATE TABLE "platform_setting_audits" (
  "id" UUID NOT NULL,
  "actor_id" UUID NOT NULL,
  "action" TEXT NOT NULL,
  "changed_fields" TEXT[] NOT NULL,
  "previous_value" JSONB,
  "new_value" JSONB,
  "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "platform_setting_audits_pkey" PRIMARY KEY ("id"),
  CONSTRAINT "platform_setting_audits_actor_id_fkey" FOREIGN KEY ("actor_id") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE INDEX "platform_setting_audits_actor_id_created_at_idx" ON "platform_setting_audits"("actor_id", "created_at");
CREATE INDEX "platform_setting_audits_action_created_at_idx" ON "platform_setting_audits"("action", "created_at");

INSERT INTO "platform_settings"("id", "smtp_host", "smtp_port", "smtp_sender_email")
VALUES ('global', 'mailpit', 1025, 'no-reply@adverse.example.com')
ON CONFLICT ("id") DO NOTHING;
