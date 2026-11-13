INSERT INTO "role_permissions" ("role_id", "module_id", "permission_id", "created_at")
SELECT role_record."id", module_record."id", permission_record."id", CURRENT_TIMESTAMP
FROM "roles" role_record
JOIN "modules" module_record ON module_record."code" = 'CRM'
JOIN "permissions" permission_record
  ON permission_record."code" IN ('VIEW', 'CREATE', 'EDIT')
WHERE role_record."code" = 'COMPANY_ADMIN'
ON CONFLICT ("role_id", "module_id", "permission_id") DO NOTHING;
