-- Owner requests 2026-11-28.
-- 1. An invoice belongs to one payment sheet by its number, not its start date: two payments on
--    the same day open two sheets, and each needs its own invoice. `carried_in` is the budget left
--    (or extra used) brought in from the sheet before, shown as the invoice's first line.
ALTER TABLE "invoices" ADD COLUMN "sheet_index" INTEGER;
ALTER TABLE "invoices" ADD COLUMN "carried_in" DECIMAL(12,2) NOT NULL DEFAULT 0;

-- 2. Invoice numbers are never given out twice, even after a draft is deleted.
CREATE TABLE "invoice_counters" (
  "company_id" UUID NOT NULL,
  "last_number" INTEGER NOT NULL DEFAULT 0,
  CONSTRAINT "invoice_counters_pkey" PRIMARY KEY ("company_id"),
  CONSTRAINT "invoice_counters_company_id_fkey" FOREIGN KEY ("company_id")
    REFERENCES "companies"("id") ON DELETE CASCADE ON UPDATE CASCADE
);
INSERT INTO "invoice_counters" ("company_id", "last_number")
SELECT "company_id", MAX("number") FROM "invoices" GROUP BY "company_id";

-- 3. Mailbox tab chosen by the app: PRIMARY or UPDATES. NULL keeps the old rule (mail from a
--    person goes to Primary, mail from Adverse to Updates).
ALTER TABLE "mail_messages" ADD COLUMN "category" VARCHAR(12);
