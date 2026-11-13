ALTER TABLE "users"
  ADD COLUMN "department_id" UUID,
  ADD COLUMN "branch_id" UUID,
  ADD CONSTRAINT "users_department_id_fkey" FOREIGN KEY ("department_id") REFERENCES "departments"("id") ON DELETE SET NULL ON UPDATE CASCADE,
  ADD CONSTRAINT "users_branch_id_fkey" FOREIGN KEY ("branch_id") REFERENCES "branches"("id") ON DELETE SET NULL ON UPDATE CASCADE;

CREATE INDEX "users_department_id_idx" ON "users"("department_id");
CREATE INDEX "users_branch_id_idx" ON "users"("branch_id");

INSERT INTO "role_permissions" ("role_id","module_id","permission_id")
SELECT r.id,m.id,p.id FROM roles r CROSS JOIN modules m CROSS JOIN permissions p
WHERE r.code='COMPANY_ADMIN' AND m.code='USERS' AND p.code IN ('VIEW','MANAGE')
ON CONFLICT ("role_id","module_id","permission_id") DO NOTHING;
