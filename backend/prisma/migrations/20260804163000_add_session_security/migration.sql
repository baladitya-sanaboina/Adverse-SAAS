CREATE TYPE "AuthenticationEventType" AS ENUM (
    'LOGIN_SUCCESS', 'LOGIN_FAILED', 'REFRESH_USED', 'LOGOUT',
    'TOKEN_REVOKED', 'SESSION_EXPIRED'
);

ALTER TABLE "auth_sessions" ADD COLUMN "company_id" UUID;
UPDATE "auth_sessions" s SET "company_id" = u."company_id"
FROM "users" u WHERE u."id" = s."user_id";

CREATE TABLE "authentication_events" (
    "id" UUID NOT NULL,
    "event_type" "AuthenticationEventType" NOT NULL,
    "user_id" UUID,
    "session_id" UUID,
    "email" TEXT,
    "details" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "authentication_events_pkey" PRIMARY KEY ("id")
);

CREATE INDEX "auth_sessions_company_id_idx" ON "auth_sessions"("company_id");
CREATE INDEX "authentication_events_user_id_idx" ON "authentication_events"("user_id");
CREATE INDEX "authentication_events_session_id_idx" ON "authentication_events"("session_id");
CREATE INDEX "authentication_events_event_type_created_at_idx" ON "authentication_events"("event_type", "created_at");

ALTER TABLE "auth_sessions" ADD CONSTRAINT "auth_sessions_company_id_fkey"
FOREIGN KEY ("company_id") REFERENCES "companies"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
ALTER TABLE "authentication_events" ADD CONSTRAINT "authentication_events_user_id_fkey"
FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;
ALTER TABLE "authentication_events" ADD CONSTRAINT "authentication_events_session_id_fkey"
FOREIGN KEY ("session_id") REFERENCES "auth_sessions"("id") ON DELETE SET NULL ON UPDATE CASCADE;
