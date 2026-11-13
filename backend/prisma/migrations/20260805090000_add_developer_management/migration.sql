CREATE TABLE "user_permissions" (
  "user_id" UUID NOT NULL,
  "module_id" UUID NOT NULL,
  "permission_id" UUID NOT NULL,
  "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "user_permissions_pkey" PRIMARY KEY ("user_id", "module_id", "permission_id")
);

CREATE INDEX "user_permissions_module_id_idx" ON "user_permissions"("module_id");
CREATE INDEX "user_permissions_permission_id_idx" ON "user_permissions"("permission_id");
ALTER TABLE "user_permissions" ADD CONSTRAINT "user_permissions_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "user_permissions" ADD CONSTRAINT "user_permissions_module_id_fkey" FOREIGN KEY ("module_id") REFERENCES "modules"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "user_permissions" ADD CONSTRAINT "user_permissions_permission_id_fkey" FOREIGN KEY ("permission_id") REFERENCES "permissions"("id") ON DELETE CASCADE ON UPDATE CASCADE;

CREATE TABLE "developer_audits" (
  "id" UUID NOT NULL,
  "actor_id" UUID NOT NULL,
  "target_developer_id" UUID NOT NULL,
  "action" TEXT NOT NULL,
  "details" TEXT,
  "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "developer_audits_pkey" PRIMARY KEY ("id")
);

CREATE INDEX "developer_audits_actor_id_created_at_idx" ON "developer_audits"("actor_id", "created_at");
CREATE INDEX "developer_audits_target_developer_id_created_at_idx" ON "developer_audits"("target_developer_id", "created_at");
ALTER TABLE "developer_audits" ADD CONSTRAINT "developer_audits_actor_id_fkey" FOREIGN KEY ("actor_id") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
ALTER TABLE "developer_audits" ADD CONSTRAINT "developer_audits_target_developer_id_fkey" FOREIGN KEY ("target_developer_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
