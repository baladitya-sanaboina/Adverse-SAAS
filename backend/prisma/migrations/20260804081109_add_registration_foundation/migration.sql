-- CreateEnum
CREATE TYPE "RegistrationAction" AS ENUM ('USER_CREATED', 'COMPANY_CREATED');

-- CreateTable
CREATE TABLE "registration_audits" (
    "id" UUID NOT NULL,
    "action" "RegistrationAction" NOT NULL,
    "actor_id" UUID NOT NULL,
    "created_user_id" UUID,
    "company_id" UUID,
    "role_code" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "registration_audits_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "registration_audits_actor_id_idx" ON "registration_audits"("actor_id");

-- CreateIndex
CREATE INDEX "registration_audits_created_user_id_idx" ON "registration_audits"("created_user_id");

-- CreateIndex
CREATE INDEX "registration_audits_company_id_idx" ON "registration_audits"("company_id");

-- AddForeignKey
ALTER TABLE "registration_audits" ADD CONSTRAINT "registration_audits_actor_id_fkey" FOREIGN KEY ("actor_id") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "registration_audits" ADD CONSTRAINT "registration_audits_created_user_id_fkey" FOREIGN KEY ("created_user_id") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "registration_audits" ADD CONSTRAINT "registration_audits_company_id_fkey" FOREIGN KEY ("company_id") REFERENCES "companies"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
