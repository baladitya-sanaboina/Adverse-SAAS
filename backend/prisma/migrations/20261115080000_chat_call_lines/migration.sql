-- Call lines in a chat link to their call (owner request 2026-11-15): the chat shows a call card
-- that joins a call still running, and "Missed call" to people who never joined it.
ALTER TABLE "chat_messages" ADD COLUMN "call_id" UUID;
ALTER TABLE "chat_messages" ADD COLUMN "call_event" VARCHAR(10);
ALTER TABLE "chat_messages" ADD COLUMN "call_joined" JSONB;
ALTER TABLE "chat_messages" ADD CONSTRAINT "chat_messages_call_id_fkey"
  FOREIGN KEY ("call_id") REFERENCES "chat_calls"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- No emojis in the app's own lines (owner request 2026-11-15).
UPDATE "chat_messages" SET "body" = substr("body", 3) WHERE "body" LIKE '📞 %';
