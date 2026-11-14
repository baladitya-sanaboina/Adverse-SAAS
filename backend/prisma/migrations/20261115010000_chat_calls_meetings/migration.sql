-- Chat calls and scheduled meetings (owner request 2026-11-14). Additive only.

-- CreateEnum
CREATE TYPE "ChatCallKind" AS ENUM ('AUDIO', 'VIDEO');

-- CreateTable
CREATE TABLE "chat_calls" (
    "id" UUID NOT NULL,
    "company_id" UUID NOT NULL,
    "conversation_id" UUID NOT NULL,
    "kind" "ChatCallKind" NOT NULL,
    "started_by_id" UUID NOT NULL,
    "started_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "ended_at" TIMESTAMP(3),

CONSTRAINT "chat_calls_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "chat_call_participants" (
    "id" UUID NOT NULL,
    "call_id" UUID NOT NULL,
    "user_id" UUID NOT NULL,
    "joined_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "last_seen_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "left_at" TIMESTAMP(3),

CONSTRAINT "chat_call_participants_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "chat_meetings" (
    "id" UUID NOT NULL,
    "company_id" UUID NOT NULL,
    "conversation_id" UUID NOT NULL,
    "title" VARCHAR(160) NOT NULL,
    "notes" VARCHAR(1000) NOT NULL DEFAULT '',
    "starts_at" TIMESTAMP(3) NOT NULL,
    "duration_minutes" INTEGER NOT NULL DEFAULT 30,
    "kind" "ChatCallKind" NOT NULL DEFAULT 'VIDEO',
    "created_by_id" UUID NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "cancelled_at" TIMESTAMP(3),

CONSTRAINT "chat_meetings_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "chat_calls_conversation_id_ended_at_idx" ON "chat_calls"("conversation_id", "ended_at");

-- CreateIndex
CREATE UNIQUE INDEX "chat_call_participants_call_id_user_id_key" ON "chat_call_participants"("call_id", "user_id");

-- CreateIndex
CREATE INDEX "chat_meetings_company_id_starts_at_idx" ON "chat_meetings"("company_id", "starts_at");

-- CreateIndex
CREATE INDEX "chat_meetings_conversation_id_starts_at_idx" ON "chat_meetings"("conversation_id", "starts_at");

-- AddForeignKey
ALTER TABLE "chat_calls" ADD CONSTRAINT "chat_calls_conversation_id_fkey" FOREIGN KEY ("conversation_id") REFERENCES "chat_conversations"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "chat_calls" ADD CONSTRAINT "chat_calls_started_by_id_fkey" FOREIGN KEY ("started_by_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "chat_call_participants" ADD CONSTRAINT "chat_call_participants_call_id_fkey" FOREIGN KEY ("call_id") REFERENCES "chat_calls"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "chat_call_participants" ADD CONSTRAINT "chat_call_participants_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "chat_meetings" ADD CONSTRAINT "chat_meetings_conversation_id_fkey" FOREIGN KEY ("conversation_id") REFERENCES "chat_conversations"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "chat_meetings" ADD CONSTRAINT "chat_meetings_created_by_id_fkey" FOREIGN KEY ("created_by_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
