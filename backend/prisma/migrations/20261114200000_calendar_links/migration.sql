-- Content calendar links (owner request 2026-11-14): the sheet's "Script" and "PDF's LINKS"
-- columns are links the client types in. Additive only.

-- AlterTable
ALTER TABLE "content_calendar_entries" ADD COLUMN     "pdf_url" VARCHAR(1000) NOT NULL DEFAULT '',
ADD COLUMN     "script_url" VARCHAR(1000) NOT NULL DEFAULT '';
