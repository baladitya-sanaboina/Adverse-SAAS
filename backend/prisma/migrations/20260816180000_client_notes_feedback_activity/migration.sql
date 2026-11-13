CREATE TABLE "client_notes" (
    "id" UUID NOT NULL,
    "company_id" UUID NOT NULL,
    "client_id" UUID NOT NULL,
    "created_by_id" UUID NOT NULL,
    "content" TEXT NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,
    CONSTRAINT "client_notes_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "client_feedback" (
    "id" UUID NOT NULL,
    "company_id" UUID NOT NULL,
    "client_id" UUID NOT NULL,
    "created_by_id" UUID NOT NULL,
    "content" TEXT NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,
    CONSTRAINT "client_feedback_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "client_activities" (
    "id" UUID NOT NULL,
    "company_id" UUID NOT NULL,
    "client_id" UUID NOT NULL,
    "actor_id" UUID NOT NULL,
    "type" TEXT NOT NULL,
    "description" TEXT NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "client_activities_pkey" PRIMARY KEY ("id")
);

CREATE INDEX "client_notes_company_id_client_id_created_at_idx"
ON "client_notes"("company_id", "client_id", "created_at");
CREATE INDEX "client_notes_created_by_id_idx" ON "client_notes"("created_by_id");
CREATE INDEX "client_feedback_company_id_client_id_created_at_idx"
ON "client_feedback"("company_id", "client_id", "created_at");
CREATE INDEX "client_feedback_created_by_id_idx" ON "client_feedback"("created_by_id");
CREATE INDEX "client_activities_company_id_client_id_created_at_idx"
ON "client_activities"("company_id", "client_id", "created_at");
CREATE INDEX "client_activities_actor_id_idx" ON "client_activities"("actor_id");

ALTER TABLE "client_notes" ADD CONSTRAINT "client_notes_company_id_fkey"
FOREIGN KEY ("company_id") REFERENCES "companies"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "client_notes" ADD CONSTRAINT "client_notes_client_id_fkey"
FOREIGN KEY ("client_id") REFERENCES "clients"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "client_notes" ADD CONSTRAINT "client_notes_created_by_id_fkey"
FOREIGN KEY ("created_by_id") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE "client_feedback" ADD CONSTRAINT "client_feedback_company_id_fkey"
FOREIGN KEY ("company_id") REFERENCES "companies"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "client_feedback" ADD CONSTRAINT "client_feedback_client_id_fkey"
FOREIGN KEY ("client_id") REFERENCES "clients"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "client_feedback" ADD CONSTRAINT "client_feedback_created_by_id_fkey"
FOREIGN KEY ("created_by_id") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE "client_activities" ADD CONSTRAINT "client_activities_company_id_fkey"
FOREIGN KEY ("company_id") REFERENCES "companies"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "client_activities" ADD CONSTRAINT "client_activities_client_id_fkey"
FOREIGN KEY ("client_id") REFERENCES "clients"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "client_activities" ADD CONSTRAINT "client_activities_actor_id_fkey"
FOREIGN KEY ("actor_id") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
