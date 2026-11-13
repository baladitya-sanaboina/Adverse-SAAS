ALTER TABLE "company_tenant_defaults"
  ADD COLUMN "accent_color" TEXT NOT NULL DEFAULT '#3D9BF5',
  ADD COLUMN "info_color" TEXT NOT NULL DEFAULT '#2563A6',
  ADD COLUMN "success_color" TEXT NOT NULL DEFAULT '#16855B',
  ADD COLUMN "warning_color" TEXT NOT NULL DEFAULT '#B7791F',
  ADD COLUMN "danger_color" TEXT NOT NULL DEFAULT '#C2414F';

ALTER TABLE "company_tenant_defaults"
  ADD CONSTRAINT "company_tenant_defaults_accent_color" CHECK ("accent_color" ~ '^#[0-9A-Fa-f]{6}$'),
  ADD CONSTRAINT "company_tenant_defaults_info_color" CHECK ("info_color" ~ '^#[0-9A-Fa-f]{6}$'),
  ADD CONSTRAINT "company_tenant_defaults_success_color" CHECK ("success_color" ~ '^#[0-9A-Fa-f]{6}$'),
  ADD CONSTRAINT "company_tenant_defaults_warning_color" CHECK ("warning_color" ~ '^#[0-9A-Fa-f]{6}$'),
  ADD CONSTRAINT "company_tenant_defaults_danger_color" CHECK ("danger_color" ~ '^#[0-9A-Fa-f]{6}$');
