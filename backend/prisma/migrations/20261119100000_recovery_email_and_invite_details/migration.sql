-- Owner request 2026-11-19. Everyone logs in with an internal address (name@adverseindia.com)
-- that only exists inside the app; their own Gmail is where outside mail goes: account setup,
-- password reset, salary and documents. Invitations also take designation, department and
-- joining date for employees and managers.

ALTER TABLE "users" ADD COLUMN "recovery_email" TEXT;
CREATE INDEX "users_recovery_email_idx" ON "users"(LOWER("recovery_email"));

-- People who already accepted an invitation: their Gmail was only on the invitation.
UPDATE "users" u SET "recovery_email" = LOWER(i."notification_email")
FROM (
    SELECT DISTINCT ON ("user_id") "user_id", "notification_email"
    FROM "company_invitations"
    WHERE "user_id" IS NOT NULL AND "notification_email" IS NOT NULL
    ORDER BY "user_id", "created_at" DESC
) i
WHERE u."id" = i."user_id" AND u."recovery_email" IS NULL
  AND LOWER(i."notification_email") <> LOWER(u."email");

ALTER TABLE "employees" ADD COLUMN "designation" VARCHAR(120) NOT NULL DEFAULT '';
ALTER TABLE "employees" ADD COLUMN "joining_date" DATE;

ALTER TABLE "company_invitations" ADD COLUMN "designation" VARCHAR(120);
ALTER TABLE "company_invitations" ADD COLUMN "department_id" UUID;
ALTER TABLE "company_invitations" ADD COLUMN "joining_date" DATE;
ALTER TABLE "company_invitations" ADD CONSTRAINT "company_invitations_department_id_fkey"
  FOREIGN KEY ("department_id") REFERENCES "departments"("id") ON DELETE SET NULL ON UPDATE CASCADE;
