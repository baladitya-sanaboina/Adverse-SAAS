-- Meet links for chats and a lobby for people outside the chat (owner request 2026-11-14).
CREATE TYPE "ChatCallAdmissionStatus" AS ENUM ('WAITING', 'ADMITTED', 'DENIED');

ALTER TABLE "chat_conversations" ADD COLUMN "meet_code" VARCHAR(16);
CREATE UNIQUE INDEX "chat_conversations_meet_code_key" ON "chat_conversations"("meet_code");

CREATE TABLE "chat_call_admissions" (
    "id" UUID NOT NULL,
    "call_id" UUID NOT NULL,
    "user_id" UUID NOT NULL,
    "status" "ChatCallAdmissionStatus" NOT NULL DEFAULT 'WAITING',
    "requested_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "last_seen_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "decided_at" TIMESTAMP(3),
    "decided_by_id" UUID,

    CONSTRAINT "chat_call_admissions_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "chat_call_admissions_call_id_user_id_key" ON "chat_call_admissions"("call_id", "user_id");

ALTER TABLE "chat_call_admissions" ADD CONSTRAINT "chat_call_admissions_call_id_fkey" FOREIGN KEY ("call_id") REFERENCES "chat_calls"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "chat_call_admissions" ADD CONSTRAINT "chat_call_admissions_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "chat_call_admissions" ADD CONSTRAINT "chat_call_admissions_decided_by_id_fkey" FOREIGN KEY ("decided_by_id") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;
