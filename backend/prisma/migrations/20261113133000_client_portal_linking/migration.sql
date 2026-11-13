ALTER TABLE "clients"
ADD COLUMN "user_id" UUID;

ALTER TABLE "clients"
ADD CONSTRAINT "clients_user_id_fkey"
FOREIGN KEY ("user_id") REFERENCES "users"("id")
ON DELETE SET NULL
ON UPDATE CASCADE;

CREATE UNIQUE INDEX "clients_user_id_key" ON "clients"("user_id");
CREATE INDEX "clients_company_id_email_idx" ON "clients"("company_id", "email");
CREATE UNIQUE INDEX "clients_company_email_unique_ci" ON "clients" ("company_id", LOWER("email")) WHERE "email" IS NOT NULL;

WITH ranked_client_users AS (
  SELECT
    c.id AS client_id,
    u.id AS user_id,
    ROW_NUMBER() OVER (PARTITION BY c.id ORDER BY u.created_at ASC, u.id ASC) AS match_rank
  FROM clients c
  JOIN users u ON u.company_id = c.company_id AND LOWER(u.email) = LOWER(c.email)
  JOIN roles r ON r.id = u.role_id AND r.code = 'COMPANY_CLIENT'
  WHERE c.email IS NOT NULL
)
UPDATE clients c
SET user_id = matched.user_id
FROM ranked_client_users matched
WHERE matched.client_id = c.id
  AND matched.match_rank = 1
  AND c.user_id IS NULL;
