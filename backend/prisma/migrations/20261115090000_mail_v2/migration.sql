-- Mail v2 (owner request 2026-11-15): a Gmail-style mailbox in its own tab. To/Cc/Bcc, star,
-- archive, trash and "delete forever", drafts, schedule send, and tickets raised from mail.

-- SENT, SCHEDULED (goes out at scheduled_at) or DRAFT (only the sender sees it).
ALTER TABLE "mail_messages" ADD COLUMN "status" VARCHAR(12) NOT NULL DEFAULT 'SENT';
ALTER TABLE "mail_messages" ADD COLUMN "scheduled_at" TIMESTAMP(3);
ALTER TABLE "mail_messages" ADD COLUMN "sender_starred_at" TIMESTAMP(3);
ALTER TABLE "mail_messages" ADD COLUMN "sender_purged_at" TIMESTAMP(3);
CREATE INDEX "mail_messages_status_scheduled_at_idx" ON "mail_messages"("status", "scheduled_at");

-- TO, CC or BCC. Archive hides from the inbox; deleted_at is the trash; purged_at is gone.
ALTER TABLE "mail_recipients" ADD COLUMN "kind" VARCHAR(3) NOT NULL DEFAULT 'TO';
ALTER TABLE "mail_recipients" ADD COLUMN "starred_at" TIMESTAMP(3);
ALTER TABLE "mail_recipients" ADD COLUMN "archived_at" TIMESTAMP(3);
ALTER TABLE "mail_recipients" ADD COLUMN "purged_at" TIMESTAMP(3);

-- A problem raised from mail. The conversation is the mail thread; the admin assigns and closes.
CREATE TABLE "mail_tickets" (
    "id" UUID NOT NULL,
    "company_id" UUID NOT NULL,
    "number" INTEGER NOT NULL,
    "thread_id" UUID NOT NULL,
    "subject" VARCHAR(200) NOT NULL,
    "priority" VARCHAR(10) NOT NULL DEFAULT 'NORMAL',
    "status" VARCHAR(12) NOT NULL DEFAULT 'OPEN',
    "raised_by_id" UUID,
    "assignee_id" UUID,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "closed_at" TIMESTAMP(3),

    CONSTRAINT "mail_tickets_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "mail_tickets_thread_id_key" ON "mail_tickets"("thread_id");
CREATE UNIQUE INDEX "mail_tickets_company_id_number_key" ON "mail_tickets"("company_id", "number");
CREATE INDEX "mail_tickets_company_id_status_idx" ON "mail_tickets"("company_id", "status");

ALTER TABLE "mail_tickets" ADD CONSTRAINT "mail_tickets_company_id_fkey" FOREIGN KEY ("company_id") REFERENCES "companies"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "mail_tickets" ADD CONSTRAINT "mail_tickets_raised_by_id_fkey" FOREIGN KEY ("raised_by_id") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;
ALTER TABLE "mail_tickets" ADD CONSTRAINT "mail_tickets_assignee_id_fkey" FOREIGN KEY ("assignee_id") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;
