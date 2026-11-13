CREATE TYPE "LeadSource" AS ENUM ('WEBSITE', 'REFERRAL', 'EMAIL', 'PHONE', 'SOCIAL', 'OTHER');
CREATE TYPE "LeadStatus" AS ENUM ('NEW', 'CONTACTED', 'QUALIFIED', 'LOST', 'CONVERTED');
CREATE TYPE "OpportunityStage" AS ENUM ('NEW', 'QUALIFIED', 'PROPOSAL', 'NEGOTIATION', 'WON', 'LOST');
CREATE TYPE "OpportunityStatus" AS ENUM ('OPEN', 'CLOSED');

CREATE TABLE "leads" (
    "id" UUID NOT NULL,
    "company_id" UUID NOT NULL,
    "client_id" UUID,
    "owner_id" UUID NOT NULL,
    "name" TEXT NOT NULL,
    "company_name" TEXT NOT NULL DEFAULT '',
    "email" TEXT,
    "phone" TEXT,
    "source" "LeadSource" NOT NULL DEFAULT 'OTHER',
    "status" "LeadStatus" NOT NULL DEFAULT 'NEW',
    "notes" TEXT NOT NULL DEFAULT '',
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "leads_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "opportunities" (
    "id" UUID NOT NULL,
    "company_id" UUID NOT NULL,
    "client_id" UUID NOT NULL,
    "lead_id" UUID,
    "owner_id" UUID NOT NULL,
    "name" TEXT NOT NULL,
    "description" TEXT NOT NULL DEFAULT '',
    "value" DECIMAL(18,2) NOT NULL DEFAULT 0,
    "currency" VARCHAR(3) NOT NULL DEFAULT 'INR',
    "stage" "OpportunityStage" NOT NULL DEFAULT 'NEW',
    "status" "OpportunityStatus" NOT NULL DEFAULT 'OPEN',
    "expected_close_date" DATE,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "opportunities_pkey" PRIMARY KEY ("id"),
    CONSTRAINT "opportunities_value_check" CHECK ("value" >= 0),
    CONSTRAINT "opportunities_currency_check" CHECK ("currency" ~ '^[A-Z]{3}$'),
    CONSTRAINT "opportunities_stage_status_check" CHECK (
        ("stage" IN ('WON', 'LOST') AND "status" = 'CLOSED') OR
        ("stage" NOT IN ('WON', 'LOST') AND "status" = 'OPEN')
    )
);

CREATE TABLE "crm_audits" (
    "id" UUID NOT NULL,
    "company_id" UUID NOT NULL,
    "actor_id" UUID NOT NULL,
    "entity_type" TEXT NOT NULL,
    "entity_id" UUID NOT NULL,
    "action" TEXT NOT NULL,
    "details" JSONB,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "crm_audits_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "leads_company_id_email_key" ON "leads"("company_id", "email");
CREATE INDEX "leads_company_id_status_idx" ON "leads"("company_id", "status");
CREATE INDEX "leads_company_id_owner_id_idx" ON "leads"("company_id", "owner_id");
CREATE INDEX "leads_company_id_source_idx" ON "leads"("company_id", "source");
CREATE INDEX "leads_client_id_idx" ON "leads"("client_id");

CREATE INDEX "opportunities_company_id_stage_idx" ON "opportunities"("company_id", "stage");
CREATE INDEX "opportunities_company_id_status_idx" ON "opportunities"("company_id", "status");
CREATE INDEX "opportunities_company_id_owner_id_idx" ON "opportunities"("company_id", "owner_id");
CREATE INDEX "opportunities_client_id_idx" ON "opportunities"("client_id");
CREATE INDEX "opportunities_lead_id_idx" ON "opportunities"("lead_id");

CREATE INDEX "crm_audits_company_id_created_at_idx" ON "crm_audits"("company_id", "created_at");
CREATE INDEX "crm_audits_entity_type_entity_id_idx" ON "crm_audits"("entity_type", "entity_id");

ALTER TABLE "leads"
ADD CONSTRAINT "leads_company_id_fkey"
FOREIGN KEY ("company_id") REFERENCES "companies"("id") ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE "leads"
ADD CONSTRAINT "leads_client_id_fkey"
FOREIGN KEY ("client_id") REFERENCES "clients"("id") ON DELETE SET NULL ON UPDATE CASCADE;

ALTER TABLE "leads"
ADD CONSTRAINT "leads_owner_id_fkey"
FOREIGN KEY ("owner_id") REFERENCES "employees"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE "opportunities"
ADD CONSTRAINT "opportunities_company_id_fkey"
FOREIGN KEY ("company_id") REFERENCES "companies"("id") ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE "opportunities"
ADD CONSTRAINT "opportunities_client_id_fkey"
FOREIGN KEY ("client_id") REFERENCES "clients"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE "opportunities"
ADD CONSTRAINT "opportunities_lead_id_fkey"
FOREIGN KEY ("lead_id") REFERENCES "leads"("id") ON DELETE SET NULL ON UPDATE CASCADE;

ALTER TABLE "opportunities"
ADD CONSTRAINT "opportunities_owner_id_fkey"
FOREIGN KEY ("owner_id") REFERENCES "employees"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE "crm_audits"
ADD CONSTRAINT "crm_audits_company_id_fkey"
FOREIGN KEY ("company_id") REFERENCES "companies"("id") ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE "crm_audits"
ADD CONSTRAINT "crm_audits_actor_id_fkey"
FOREIGN KEY ("actor_id") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
