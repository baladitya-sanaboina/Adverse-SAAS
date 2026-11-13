CREATE TYPE "InvitationStatus" AS ENUM ('PENDING','ACCEPTED','EXPIRED','REVOKED');

CREATE TABLE "company_invitations" (
  "id" UUID NOT NULL,
  "company_id" UUID NOT NULL,
  "email" TEXT NOT NULL,
  "invited_by" UUID NOT NULL,
  "token_hash" TEXT NOT NULL,
  "expires_at" TIMESTAMP(3) NOT NULL,
  "accepted_at" TIMESTAMP(3),
  "status" "InvitationStatus" NOT NULL DEFAULT 'PENDING',
  "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "company_invitations_pkey" PRIMARY KEY ("id"),
  CONSTRAINT "company_invitations_company_id_fkey" FOREIGN KEY ("company_id") REFERENCES "companies"("id") ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT "company_invitations_invited_by_fkey" FOREIGN KEY ("invited_by") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE
);
CREATE UNIQUE INDEX "company_invitations_token_hash_key" ON "company_invitations"("token_hash");
CREATE UNIQUE INDEX "company_invitations_pending_email_key" ON "company_invitations"("company_id",LOWER("email")) WHERE "status"='PENDING';
CREATE INDEX "company_invitations_company_id_status_idx" ON "company_invitations"("company_id","status");
CREATE INDEX "company_invitations_company_id_email_idx" ON "company_invitations"("company_id","email");
CREATE INDEX "company_invitations_expires_at_idx" ON "company_invitations"("expires_at");

CREATE TABLE "invitation_audits" (
  "id" UUID NOT NULL,
  "invitation_id" UUID NOT NULL,
  "company_id" UUID NOT NULL,
  "actor_id" UUID,
  "action" TEXT NOT NULL,
  "details" JSONB,
  "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "invitation_audits_pkey" PRIMARY KEY ("id"),
  CONSTRAINT "invitation_audits_invitation_id_fkey" FOREIGN KEY ("invitation_id") REFERENCES "company_invitations"("id") ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT "invitation_audits_company_id_fkey" FOREIGN KEY ("company_id") REFERENCES "companies"("id") ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT "invitation_audits_actor_id_fkey" FOREIGN KEY ("actor_id") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE
);
CREATE INDEX "invitation_audits_company_id_created_at_idx" ON "invitation_audits"("company_id","created_at");
CREATE INDEX "invitation_audits_invitation_id_created_at_idx" ON "invitation_audits"("invitation_id","created_at");

INSERT INTO "modules" ("id","name","code","created_at","updated_at") VALUES
  (gen_random_uuid(),'Invitations','INVITATIONS',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)
ON CONFLICT ("code") DO NOTHING;
INSERT INTO "role_permissions" ("role_id","module_id","permission_id")
SELECT r.id,m.id,p.id FROM roles r CROSS JOIN modules m CROSS JOIN permissions p
WHERE r.code='COMPANY_ADMIN' AND m.code='INVITATIONS' AND p.code IN ('VIEW','CREATE','MANAGE')
ON CONFLICT ("role_id","module_id","permission_id") DO NOTHING;
