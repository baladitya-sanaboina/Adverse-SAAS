-- Chat changes (owner request 2026-11-14): the admin creates client rooms by hand and picks who
-- is in them, so rooms are no longer one per client and client_access (empty, added in the
-- previous migration) is replaced by room members. Adds the chat status people set.

-- CreateEnum
CREATE TYPE "ChatStatusValue" AS ENUM ('AVAILABLE', 'BUSY', 'AWAY');

-- DropForeignKey
ALTER TABLE "client_access" DROP CONSTRAINT "client_access_client_id_fkey";

-- DropForeignKey
ALTER TABLE "client_access" DROP CONSTRAINT "client_access_company_id_fkey";

-- DropForeignKey
ALTER TABLE "client_access" DROP CONSTRAINT "client_access_granted_by_id_fkey";

-- DropForeignKey
ALTER TABLE "client_access" DROP CONSTRAINT "client_access_user_id_fkey";

-- DropIndex
DROP INDEX "chat_conversations_client_id_key";

-- DropTable
DROP TABLE "client_access";

-- CreateTable
CREATE TABLE "chat_statuses" (
    "user_id" UUID NOT NULL,
    "status" "ChatStatusValue" NOT NULL DEFAULT 'AVAILABLE',
    "updated_at" TIMESTAMP(3) NOT NULL,

CONSTRAINT "chat_statuses_pkey" PRIMARY KEY ("user_id")
);

-- CreateIndex
CREATE INDEX "chat_conversations_client_id_idx" ON "chat_conversations"("client_id");

-- AddForeignKey
ALTER TABLE "chat_statuses" ADD CONSTRAINT "chat_statuses_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
