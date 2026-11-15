-- Calendar with events and todos for the admin, managers and employees (owner request
-- 2026-11-15). Separate from the Content Calendar. Video events hold their meeting in a chat;
-- an event can come from a mail conversation; alerts go out 10 minutes before and at the start.
CREATE TABLE "agenda_events" (
    "id" UUID NOT NULL,
    "company_id" UUID NOT NULL,
    "owner_id" UUID NOT NULL,
    "title" VARCHAR(160) NOT NULL,
    "notes" VARCHAR(2000) NOT NULL DEFAULT '',
    "location" VARCHAR(200) NOT NULL DEFAULT '',
    "starts_at" TIMESTAMP(3) NOT NULL,
    "ends_at" TIMESTAMP(3) NOT NULL,
    "all_day" BOOLEAN NOT NULL DEFAULT false,
    "colour" VARCHAR(12) NOT NULL DEFAULT 'blue',
    "video" BOOLEAN NOT NULL DEFAULT false,
    "conversation_id" UUID,
    "meeting_id" UUID,
    "mail_thread_id" UUID,
    "alerted_before_at" TIMESTAMP(3),
    "alerted_start_at" TIMESTAMP(3),
    "cancelled_at" TIMESTAMP(3),
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "agenda_events_pkey" PRIMARY KEY ("id")
);

CREATE INDEX "agenda_events_company_id_starts_at_idx" ON "agenda_events"("company_id", "starts_at");
CREATE INDEX "agenda_events_owner_id_starts_at_idx" ON "agenda_events"("owner_id", "starts_at");
CREATE INDEX "agenda_events_mail_thread_id_idx" ON "agenda_events"("mail_thread_id");

CREATE TABLE "agenda_attendees" (
    "id" UUID NOT NULL,
    "event_id" UUID NOT NULL,
    "user_id" UUID NOT NULL,
    "response" VARCHAR(8) NOT NULL DEFAULT 'PENDING',
    "responded_at" TIMESTAMP(3),

    CONSTRAINT "agenda_attendees_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "agenda_attendees_event_id_user_id_key" ON "agenda_attendees"("event_id", "user_id");
CREATE INDEX "agenda_attendees_user_id_idx" ON "agenda_attendees"("user_id");

CREATE TABLE "agenda_todos" (
    "id" UUID NOT NULL,
    "company_id" UUID NOT NULL,
    "owner_id" UUID NOT NULL,
    "title" VARCHAR(200) NOT NULL,
    "notes" VARCHAR(2000) NOT NULL DEFAULT '',
    "due_date" DATE,
    "due_at" TIMESTAMP(3),
    "priority" VARCHAR(8) NOT NULL DEFAULT 'NORMAL',
    "done_at" TIMESTAMP(3),
    "alerted_before_at" TIMESTAMP(3),
    "alerted_start_at" TIMESTAMP(3),
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "agenda_todos_pkey" PRIMARY KEY ("id")
);

CREATE INDEX "agenda_todos_owner_id_done_at_idx" ON "agenda_todos"("owner_id", "done_at");
CREATE INDEX "agenda_todos_company_id_due_date_idx" ON "agenda_todos"("company_id", "due_date");

ALTER TABLE "agenda_events" ADD CONSTRAINT "agenda_events_company_id_fkey" FOREIGN KEY ("company_id") REFERENCES "companies"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "agenda_events" ADD CONSTRAINT "agenda_events_owner_id_fkey" FOREIGN KEY ("owner_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "agenda_events" ADD CONSTRAINT "agenda_events_conversation_id_fkey" FOREIGN KEY ("conversation_id") REFERENCES "chat_conversations"("id") ON DELETE SET NULL ON UPDATE CASCADE;
ALTER TABLE "agenda_events" ADD CONSTRAINT "agenda_events_meeting_id_fkey" FOREIGN KEY ("meeting_id") REFERENCES "chat_meetings"("id") ON DELETE SET NULL ON UPDATE CASCADE;
ALTER TABLE "agenda_attendees" ADD CONSTRAINT "agenda_attendees_event_id_fkey" FOREIGN KEY ("event_id") REFERENCES "agenda_events"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "agenda_attendees" ADD CONSTRAINT "agenda_attendees_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "agenda_todos" ADD CONSTRAINT "agenda_todos_company_id_fkey" FOREIGN KEY ("company_id") REFERENCES "companies"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "agenda_todos" ADD CONSTRAINT "agenda_todos_owner_id_fkey" FOREIGN KEY ("owner_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
