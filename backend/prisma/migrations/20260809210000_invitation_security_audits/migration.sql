ALTER TABLE "invitation_audits"
  ALTER COLUMN "invitation_id" DROP NOT NULL,
  ALTER COLUMN "company_id" DROP NOT NULL;
