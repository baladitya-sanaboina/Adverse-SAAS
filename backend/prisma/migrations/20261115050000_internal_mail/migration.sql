-- Internal mailbox inside Chat (owner request 2026-11-15): mail between people in the company
-- (clients only with the admins) and system mail about tasks, payments and meetings.
CREATE TABLE "mail_messages" (
    "id" UUID NOT NULL,
    "company_id" UUID NOT NULL,
    "sender_id" UUID,
    "thread_id" UUID NOT NULL,
    "reply_to_id" UUID,
    "kind" VARCHAR(40) NOT NULL DEFAULT 'PERSONAL',
    "subject" VARCHAR(200) NOT NULL,
    "body" TEXT NOT NULL DEFAULT '',
    "link" VARCHAR(300) NOT NULL DEFAULT '',
    "sender_deleted_at" TIMESTAMP(3),
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "mail_messages_pkey" PRIMARY KEY ("id")
);

CREATE INDEX "mail_messages_company_id_thread_id_created_at_idx" ON "mail_messages"("company_id", "thread_id", "created_at");
CREATE INDEX "mail_messages_sender_id_created_at_idx" ON "mail_messages"("sender_id", "created_at");

CREATE TABLE "mail_recipients" (
    "id" UUID NOT NULL,
    "message_id" UUID NOT NULL,
    "user_id" UUID NOT NULL,
    "read_at" TIMESTAMP(3),
    "deleted_at" TIMESTAMP(3),
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "mail_recipients_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "mail_recipients_message_id_user_id_key" ON "mail_recipients"("message_id", "user_id");
CREATE INDEX "mail_recipients_user_id_deleted_at_created_at_idx" ON "mail_recipients"("user_id", "deleted_at", "created_at");

CREATE TABLE "mail_attachments" (
    "id" UUID NOT NULL,
    "message_id" UUID NOT NULL,
    "file_name" VARCHAR(255) NOT NULL,
    "storage_path" VARCHAR(500) NOT NULL,
    "mime_type" VARCHAR(120) NOT NULL,
    "size_bytes" INTEGER NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "mail_attachments_pkey" PRIMARY KEY ("id")
);

CREATE INDEX "mail_attachments_message_id_idx" ON "mail_attachments"("message_id");

ALTER TABLE "mail_messages" ADD CONSTRAINT "mail_messages_company_id_fkey" FOREIGN KEY ("company_id") REFERENCES "companies"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "mail_messages" ADD CONSTRAINT "mail_messages_sender_id_fkey" FOREIGN KEY ("sender_id") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;
ALTER TABLE "mail_recipients" ADD CONSTRAINT "mail_recipients_message_id_fkey" FOREIGN KEY ("message_id") REFERENCES "mail_messages"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "mail_recipients" ADD CONSTRAINT "mail_recipients_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "mail_attachments" ADD CONSTRAINT "mail_attachments_message_id_fkey" FOREIGN KEY ("message_id") REFERENCES "mail_messages"("id") ON DELETE CASCADE ON UPDATE CASCADE;
