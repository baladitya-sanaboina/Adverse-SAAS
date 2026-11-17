ALTER TABLE "company_invitations"
  ADD COLUMN "notification_email" TEXT,
  ADD COLUMN "client_id" UUID;

UPDATE "company_invitations"
SET "notification_email" = "email"
WHERE "notification_email" IS NULL;

ALTER TABLE "company_invitations"
  ADD CONSTRAINT "company_invitations_client_id_fkey"
  FOREIGN KEY ("client_id") REFERENCES "clients"("id") ON DELETE SET NULL ON UPDATE CASCADE;

CREATE INDEX "company_invitations_client_id_idx"
  ON "company_invitations"("client_id");
