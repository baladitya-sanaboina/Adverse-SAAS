ALTER TYPE "AuthenticationEventType" ADD VALUE IF NOT EXISTS 'PASSWORD_CHANGED';
ALTER TYPE "AuthenticationEventType" ADD VALUE IF NOT EXISTS 'PASSWORD_RESET';
ALTER TYPE "AuthenticationEventType" ADD VALUE IF NOT EXISTS 'EMAIL_VERIFIED';
ALTER TYPE "AuthenticationEventType" ADD VALUE IF NOT EXISTS 'ACCOUNT_LOCKED';

ALTER TABLE "users"
  ADD COLUMN "failed_login_attempts" INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN "locked_until" TIMESTAMP(3);

ALTER TABLE "authentication_events"
  ADD COLUMN "company_id" UUID,
  ADD COLUMN "ip_address" TEXT;

CREATE INDEX "authentication_events_email_ip_address_created_at_idx"
  ON "authentication_events"("email", "ip_address", "created_at");

CREATE INDEX "users_locked_until_idx" ON "users"("locked_until");
