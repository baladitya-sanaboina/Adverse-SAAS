-- Onboarding documents (owner request 2026-11-15): client welcome, onboarding form and agreement
-- (sent within 60 hours of the client being added), and employee offer, joining, welcome and
-- agreement letters. Recipients open a private link, fill the form and accept online.
CREATE TABLE "document_templates" (
    "id" UUID NOT NULL,
    "company_id" UUID NOT NULL,
    "kind" VARCHAR(40) NOT NULL,
    "subject" VARCHAR(200) NOT NULL,
    "body" TEXT NOT NULL,
    "updated_by_id" UUID,
    "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "document_templates_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "document_templates_company_id_kind_key" ON "document_templates"("company_id", "kind");

CREATE TABLE "onboarding_packets" (
    "id" UUID NOT NULL,
    "company_id" UUID NOT NULL,
    "audience" VARCHAR(20) NOT NULL,
    "client_id" UUID,
    "user_id" UUID,
    "recipient_name" VARCHAR(160) NOT NULL,
    "recipient_email" VARCHAR(254) NOT NULL,
    "documents" JSONB NOT NULL DEFAULT '[]',
    "fields" JSONB NOT NULL DEFAULT '{}',
    "token_hash" VARCHAR(64) NOT NULL,
    "status" VARCHAR(20) NOT NULL DEFAULT 'SENT',
    "expires_at" TIMESTAMP(3) NOT NULL,
    "form_data" JSONB NOT NULL DEFAULT '{}',
    "signed_name" VARCHAR(160),
    "signed_at" TIMESTAMP(3),
    "signed_ip" VARCHAR(64),
    "signed_agent" VARCHAR(300),
    "opened_at" TIMESTAMP(3),
    "sent_count" INTEGER NOT NULL DEFAULT 1,
    "created_by_id" UUID,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "onboarding_packets_pkey" PRIMARY KEY ("id"),
    CONSTRAINT "onboarding_packets_audience_check" CHECK ("audience" IN ('CLIENT', 'EMPLOYEE')),
    CONSTRAINT "onboarding_packets_status_check" CHECK ("status" IN ('SENT', 'OPENED', 'COMPLETED', 'CANCELLED'))
);

CREATE UNIQUE INDEX "onboarding_packets_token_hash_key" ON "onboarding_packets"("token_hash");
CREATE INDEX "onboarding_packets_company_id_audience_created_at_idx" ON "onboarding_packets"("company_id", "audience", "created_at");
CREATE INDEX "onboarding_packets_client_id_idx" ON "onboarding_packets"("client_id");

ALTER TABLE "document_templates" ADD CONSTRAINT "document_templates_company_id_fkey" FOREIGN KEY ("company_id") REFERENCES "companies"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "document_templates" ADD CONSTRAINT "document_templates_updated_by_id_fkey" FOREIGN KEY ("updated_by_id") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;
ALTER TABLE "onboarding_packets" ADD CONSTRAINT "onboarding_packets_company_id_fkey" FOREIGN KEY ("company_id") REFERENCES "companies"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "onboarding_packets" ADD CONSTRAINT "onboarding_packets_client_id_fkey" FOREIGN KEY ("client_id") REFERENCES "clients"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "onboarding_packets" ADD CONSTRAINT "onboarding_packets_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;
ALTER TABLE "onboarding_packets" ADD CONSTRAINT "onboarding_packets_created_by_id_fkey" FOREIGN KEY ("created_by_id") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;
