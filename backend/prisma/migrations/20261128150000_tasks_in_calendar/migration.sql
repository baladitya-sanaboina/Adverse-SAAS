-- Every task shows in its client's content calendar (owner request 2026-11-28): tasks made on
-- the Tasks page before today get their calendar row now, on the due date (else the day it was
-- approved or made), linked to the ticket. Cancelled tasks are left out.
INSERT INTO "content_calendar_entries"
  ("id", "company_id", "client_id", "entry_date", "title", "service_id", "task_id",
   "created_by_id", "created_at", "updated_at")
SELECT gen_random_uuid(), t."company_id", t."client_id",
  COALESCE(t."due_date", t."approved_at"::date, t."created_at"::date),
  LEFT(t."title", 200), t."service_id", t."id", t."created_by_id", NOW(), NOW()
FROM "tasks" t
WHERE t."status" <> 'CANCELLED'
  AND NOT EXISTS (SELECT 1 FROM "content_calendar_entries" c WHERE c."task_id" = t."id");
