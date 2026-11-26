-- Per-client access for managers and employees (owner request 2026-11-26): READ sees a client's
-- tickets and content calendar, WRITE also changes status (up to Review), comments and uploads
-- files, CREATE also adds videos to the client's calendar. One row per person and client.
CREATE TYPE "ClientAccessLevel" AS ENUM ('READ', 'WRITE', 'CREATE');

CREATE TABLE "client_access" (
    "company_id" UUID NOT NULL,
    "user_id" UUID NOT NULL,
    "client_id" UUID NOT NULL,
    "level" "ClientAccessLevel" NOT NULL,
    "granted_by_id" UUID,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,
    CONSTRAINT "client_access_pkey" PRIMARY KEY ("user_id", "client_id")
);

CREATE INDEX "client_access_company_id_client_id_idx" ON "client_access"("company_id", "client_id");

ALTER TABLE "client_access" ADD CONSTRAINT "client_access_company_id_fkey"
  FOREIGN KEY ("company_id") REFERENCES "companies"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "client_access" ADD CONSTRAINT "client_access_user_id_fkey"
  FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "client_access" ADD CONSTRAINT "client_access_client_id_fkey"
  FOREIGN KEY ("client_id") REFERENCES "clients"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "client_access" ADD CONSTRAINT "client_access_granted_by_id_fkey"
  FOREIGN KEY ("granted_by_id") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- The automatic chat group of each client: the client, the admins and everyone with access.
ALTER TABLE "chat_conversations" ADD COLUMN "is_client_group" BOOLEAN NOT NULL DEFAULT false;
CREATE UNIQUE INDEX "chat_conversations_client_group_key"
  ON "chat_conversations"("company_id", "client_id") WHERE "is_client_group";
