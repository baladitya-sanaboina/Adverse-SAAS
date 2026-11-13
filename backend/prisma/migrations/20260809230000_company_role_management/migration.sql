ALTER TABLE "roles"
  ADD COLUMN "company_id" UUID,
  ADD COLUMN "description" TEXT NOT NULL DEFAULT '',
  ADD COLUMN "status" "OrganizationStatus" NOT NULL DEFAULT 'ACTIVE',
  ADD COLUMN "is_system" BOOLEAN NOT NULL DEFAULT false;

UPDATE "roles" SET "is_system" = true WHERE "code" IN (
  'PLATFORM_OWNER', 'DEVELOPER', 'COMPANY_ADMIN', 'COMPANY_EMPLOYEE', 'COMPANY_CLIENT'
);

ALTER TABLE "roles" DROP CONSTRAINT IF EXISTS "roles_name_key";
CREATE UNIQUE INDEX "roles_company_id_name_key" ON "roles"("company_id", LOWER("name"));
CREATE INDEX "roles_company_id_status_idx" ON "roles"("company_id", "status");
ALTER TABLE "roles" ADD CONSTRAINT "roles_company_id_fkey"
  FOREIGN KEY ("company_id") REFERENCES "companies"("id") ON DELETE CASCADE ON UPDATE CASCADE;

INSERT INTO "modules" ("id", "name", "code", "created_at", "updated_at")
VALUES (gen_random_uuid(), 'Roles', 'ROLES', NOW(), NOW())
ON CONFLICT ("code") DO NOTHING;

INSERT INTO "role_permissions" ("role_id", "module_id", "permission_id", "created_at")
SELECT r.id, m.id, p.id, NOW()
FROM "roles" r
JOIN "modules" m ON m.code = 'ROLES'
JOIN "permissions" p ON p.code IN ('VIEW', 'CREATE', 'EDIT', 'DELETE', 'MANAGE')
WHERE r.code = 'COMPANY_ADMIN'
ON CONFLICT DO NOTHING;
