ALTER TABLE "employees" ALTER COLUMN "department_id" DROP NOT NULL;
ALTER TABLE "employees" ALTER COLUMN "branch_id" DROP NOT NULL;

INSERT INTO "employees" (
    "id",
    "company_id",
    "user_id",
    "employee_code",
    "department_id",
    "branch_id",
    "role_id",
    "status",
    "created_at",
    "updated_at"
)
SELECT
    gen_random_uuid(),
    u."company_id",
    u."id",
    'EMP-' || UPPER(SUBSTRING(REPLACE(u."id"::text, '-', ''), 1, 8)),
    u."department_id",
    u."branch_id",
    u."role_id",
    CASE WHEN u."status"::text = 'ACTIVE' THEN 'ACTIVE'::"EmployeeStatus" ELSE 'PENDING'::"EmployeeStatus" END,
    u."created_at",
    NOW()
FROM "users" u
JOIN "roles" r ON r."id" = u."role_id"
LEFT JOIN "employees" e ON e."user_id" = u."id"
WHERE u."company_id" IS NOT NULL
  AND (
      r."code" = 'COMPANY_EMPLOYEE'
      OR EXISTS (
          SELECT 1
          FROM "registration_audits" ra
          WHERE ra."created_user_id" = u."id"
            AND ra."action" = 'USER_CREATED'
            AND ra."role_code" = 'COMPANY_EMPLOYEE'
      )
  )
  AND e."id" IS NULL;
