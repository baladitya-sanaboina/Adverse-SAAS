CREATE TYPE "OrganizationStatus" AS ENUM ('ACTIVE', 'INACTIVE');

CREATE TABLE "departments" (
  "id" UUID NOT NULL,
  "company_id" UUID NOT NULL,
  "name" TEXT NOT NULL,
  "description" TEXT NOT NULL DEFAULT '',
  "status" "OrganizationStatus" NOT NULL DEFAULT 'ACTIVE',
  "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "departments_pkey" PRIMARY KEY ("id"),
  CONSTRAINT "departments_company_id_fkey" FOREIGN KEY ("company_id") REFERENCES "companies"("id") ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE "branches" (
  "id" UUID NOT NULL,
  "company_id" UUID NOT NULL,
  "name" TEXT NOT NULL,
  "code" TEXT NOT NULL,
  "address" TEXT NOT NULL DEFAULT '',
  "city" TEXT NOT NULL DEFAULT '',
  "state" TEXT NOT NULL DEFAULT '',
  "country" TEXT NOT NULL DEFAULT '',
  "status" "OrganizationStatus" NOT NULL DEFAULT 'ACTIVE',
  "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "branches_pkey" PRIMARY KEY ("id"),
  CONSTRAINT "branches_company_id_fkey" FOREIGN KEY ("company_id") REFERENCES "companies"("id") ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE UNIQUE INDEX "departments_company_name_ci_key" ON "departments"("company_id", LOWER("name"));
CREATE UNIQUE INDEX "departments_company_id_name_key" ON "departments"("company_id", "name");
CREATE INDEX "departments_company_id_status_idx" ON "departments"("company_id", "status");
CREATE UNIQUE INDEX "branches_company_name_ci_key" ON "branches"("company_id", LOWER("name"));
CREATE UNIQUE INDEX "branches_company_code_ci_key" ON "branches"("company_id", UPPER("code"));
CREATE UNIQUE INDEX "branches_company_id_name_key" ON "branches"("company_id", "name");
CREATE UNIQUE INDEX "branches_company_id_code_key" ON "branches"("company_id", "code");
CREATE INDEX "branches_company_id_status_idx" ON "branches"("company_id", "status");

INSERT INTO "modules" ("id", "name", "code", "created_at", "updated_at") VALUES
  (gen_random_uuid(), 'Departments', 'DEPARTMENTS', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  (gen_random_uuid(), 'Branches', 'BRANCHES', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
ON CONFLICT ("code") DO NOTHING;

INSERT INTO "role_permissions" ("role_id", "module_id", "permission_id")
SELECT r."id", m."id", p."id" FROM "roles" r CROSS JOIN "modules" m CROSS JOIN "permissions" p
WHERE r."code"='COMPANY_ADMIN' AND m."code" IN ('DEPARTMENTS','BRANCHES') AND p."code" IN ('VIEW','CREATE','EDIT','DELETE')
ON CONFLICT ("role_id", "module_id", "permission_id") DO NOTHING;
