CREATE TABLE "organization_audits" (
  "id" UUID NOT NULL,
  "action" TEXT NOT NULL,
  "actor_id" UUID NOT NULL,
  "company_id" UUID NOT NULL,
  "entity_type" TEXT NOT NULL,
  "entity_id" UUID NOT NULL,
  "details" JSONB,
  "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "organization_audits_pkey" PRIMARY KEY ("id"),
  CONSTRAINT "organization_audits_actor_id_fkey" FOREIGN KEY ("actor_id") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT "organization_audits_company_id_fkey" FOREIGN KEY ("company_id") REFERENCES "companies"("id") ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE INDEX "organization_audits_company_id_created_at_idx" ON "organization_audits"("company_id", "created_at");
CREATE INDEX "organization_audits_actor_id_created_at_idx" ON "organization_audits"("actor_id", "created_at");
CREATE INDEX "organization_audits_entity_type_entity_id_idx" ON "organization_audits"("entity_type", "entity_id");
