INSERT INTO "role_permissions" ("role_id", "module_id", "permission_id", "created_at")
SELECT role_record."id", module_record."id", permission_record."id", NOW()
FROM "roles" role_record
JOIN "modules" module_record ON module_record."code" = 'SETTINGS'
JOIN "permissions" permission_record ON permission_record."code" IN ('VIEW', 'MANAGE')
WHERE role_record."code" = 'COMPANY_ADMIN'
ON CONFLICT ("role_id", "module_id", "permission_id") DO NOTHING;
