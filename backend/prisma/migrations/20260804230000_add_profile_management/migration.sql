CREATE TYPE "ProfileAuditAction" AS ENUM ('PROFILE_UPDATED', 'PASSWORD_CHANGED', 'PROFILE_IMAGE_UPDATED');

ALTER TABLE "users"
ADD COLUMN "first_name" TEXT,
ADD COLUMN "last_name" TEXT,
ADD COLUMN "phone_number" TEXT,
ADD COLUMN "profile_image_url" TEXT,
ADD COLUMN "timezone" TEXT NOT NULL DEFAULT 'UTC',
ADD COLUMN "language" TEXT NOT NULL DEFAULT 'en',
ADD COLUMN "theme_preference" TEXT NOT NULL DEFAULT 'system',
ADD COLUMN "email_notifications" BOOLEAN NOT NULL DEFAULT true;

CREATE TABLE "profile_audits" (
  "id" UUID NOT NULL,
  "user_id" UUID NOT NULL,
  "company_id" UUID,
  "action" "ProfileAuditAction" NOT NULL,
  "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "profile_audits_pkey" PRIMARY KEY ("id")
);

CREATE INDEX "profile_audits_user_id_created_at_idx" ON "profile_audits"("user_id", "created_at");
CREATE INDEX "profile_audits_company_id_idx" ON "profile_audits"("company_id");
ALTER TABLE "profile_audits" ADD CONSTRAINT "profile_audits_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
