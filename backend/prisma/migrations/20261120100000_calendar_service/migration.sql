-- The service (Reel, Carousel, ...) of a content calendar entry, chosen when it is added
-- (owner request 2026-11-20): the task made from it uses this service, so its client price and
-- the manager's fixed rate come from the right service.
ALTER TABLE "content_calendar_entries" ADD COLUMN "service_id" UUID;
ALTER TABLE "content_calendar_entries" ADD CONSTRAINT "content_calendar_entries_service_id_fkey"
  FOREIGN KEY ("service_id") REFERENCES "company_services"("id") ON DELETE SET NULL ON UPDATE CASCADE;
