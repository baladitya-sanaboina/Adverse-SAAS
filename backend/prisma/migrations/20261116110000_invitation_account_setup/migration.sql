ALTER TABLE "company_invitations"
  ADD COLUMN "role_code" TEXT NOT NULL DEFAULT 'COMPANY_EMPLOYEE',
  ADD COLUMN "user_id" UUID;

ALTER TABLE "company_invitations"
  ADD CONSTRAINT "company_invitations_user_id_fkey"
  FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;

CREATE INDEX "company_invitations_company_id_role_code_idx"
  ON "company_invitations"("company_id","role_code");
CREATE INDEX "company_invitations_user_id_idx"
  ON "company_invitations"("user_id");
