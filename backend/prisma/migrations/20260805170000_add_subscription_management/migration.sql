CREATE TYPE "SubscriptionPlanStatus" AS ENUM ('ACTIVE', 'INACTIVE');
CREATE TYPE "CompanySubscriptionStatus" AS ENUM ('ACTIVE', 'EXPIRED', 'CANCELLED');

CREATE TABLE "subscription_plans" (
  "id" UUID NOT NULL,
  "name" TEXT NOT NULL,
  "code" TEXT NOT NULL,
  "description" TEXT,
  "monthly_price" DECIMAL(12,2) NOT NULL DEFAULT 0,
  "yearly_price" DECIMAL(12,2) NOT NULL DEFAULT 0,
  "status" "SubscriptionPlanStatus" NOT NULL DEFAULT 'ACTIVE',
  "display_order" INTEGER NOT NULL DEFAULT 0,
  "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "subscription_plans_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX "subscription_plans_code_key" ON "subscription_plans"("code");

CREATE TABLE "subscription_plan_features" (
  "plan_id" UUID NOT NULL,
  "feature_code" TEXT NOT NULL,
  "enabled" BOOLEAN NOT NULL DEFAULT false,
  CONSTRAINT "subscription_plan_features_pkey" PRIMARY KEY ("plan_id", "feature_code")
);

CREATE TABLE "subscription_plan_limits" (
  "plan_id" UUID NOT NULL,
  "limit_code" TEXT NOT NULL,
  "value" BIGINT,
  CONSTRAINT "subscription_plan_limits_pkey" PRIMARY KEY ("plan_id", "limit_code")
);

CREATE TABLE "company_subscriptions" (
  "id" UUID NOT NULL,
  "company_id" UUID NOT NULL,
  "plan_id" UUID NOT NULL,
  "status" "CompanySubscriptionStatus" NOT NULL DEFAULT 'ACTIVE',
  "activation_date" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "expiration_date" TIMESTAMP(3),
  "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "company_subscriptions_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX "company_subscriptions_company_id_key" ON "company_subscriptions"("company_id");
CREATE INDEX "company_subscriptions_plan_id_idx" ON "company_subscriptions"("plan_id");

CREATE TABLE "subscription_audits" (
  "id" UUID NOT NULL,
  "actor_id" UUID NOT NULL,
  "company_id" UUID,
  "plan_id" UUID NOT NULL,
  "action" TEXT NOT NULL,
  "details" TEXT,
  "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "subscription_audits_pkey" PRIMARY KEY ("id")
);
CREATE INDEX "subscription_audits_actor_id_created_at_idx" ON "subscription_audits"("actor_id", "created_at");
CREATE INDEX "subscription_audits_company_id_created_at_idx" ON "subscription_audits"("company_id", "created_at");
CREATE INDEX "subscription_audits_plan_id_created_at_idx" ON "subscription_audits"("plan_id", "created_at");

ALTER TABLE "subscription_plan_features" ADD CONSTRAINT "subscription_plan_features_plan_id_fkey" FOREIGN KEY ("plan_id") REFERENCES "subscription_plans"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "subscription_plan_limits" ADD CONSTRAINT "subscription_plan_limits_plan_id_fkey" FOREIGN KEY ("plan_id") REFERENCES "subscription_plans"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "company_subscriptions" ADD CONSTRAINT "company_subscriptions_company_id_fkey" FOREIGN KEY ("company_id") REFERENCES "companies"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "company_subscriptions" ADD CONSTRAINT "company_subscriptions_plan_id_fkey" FOREIGN KEY ("plan_id") REFERENCES "subscription_plans"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
ALTER TABLE "subscription_audits" ADD CONSTRAINT "subscription_audits_actor_id_fkey" FOREIGN KEY ("actor_id") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
ALTER TABLE "subscription_audits" ADD CONSTRAINT "subscription_audits_company_id_fkey" FOREIGN KEY ("company_id") REFERENCES "companies"("id") ON DELETE SET NULL ON UPDATE CASCADE;
ALTER TABLE "subscription_audits" ADD CONSTRAINT "subscription_audits_plan_id_fkey" FOREIGN KEY ("plan_id") REFERENCES "subscription_plans"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
