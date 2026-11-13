CREATE TABLE "company_management_audits" (
    "id" UUID NOT NULL,
    "actor_id" UUID NOT NULL,
    "company_id" UUID NOT NULL,
    "action" TEXT NOT NULL,
    "previous_status" TEXT,
    "new_status" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "company_management_audits_pkey" PRIMARY KEY ("id")
);

CREATE INDEX "company_management_audits_actor_id_created_at_idx" ON "company_management_audits"("actor_id", "created_at");
CREATE INDEX "company_management_audits_company_id_created_at_idx" ON "company_management_audits"("company_id", "created_at");
ALTER TABLE "company_management_audits" ADD CONSTRAINT "company_management_audits_actor_id_fkey" FOREIGN KEY ("actor_id") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
ALTER TABLE "company_management_audits" ADD CONSTRAINT "company_management_audits_company_id_fkey" FOREIGN KEY ("company_id") REFERENCES "companies"("id") ON DELETE CASCADE ON UPDATE CASCADE;
