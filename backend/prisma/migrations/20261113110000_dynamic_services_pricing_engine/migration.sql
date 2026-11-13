-- CreateEnum
CREATE TYPE "ServicePricingModel" AS ENUM (
  'PER_VIDEO',
  'PER_PIECE',
  'MONTHLY_FIXED',
  'MONTHLY_PACKAGE',
  'COMMISSION_PER_DELIVERABLE'
);

-- CreateEnum
CREATE TYPE "ServicePricingScope" AS ENUM ('CLIENT', 'MANAGER');

-- CreateTable
CREATE TABLE "company_services" (
  "id" UUID NOT NULL,
  "company_id" UUID NOT NULL,
  "name" TEXT NOT NULL,
  "code" TEXT NOT NULL,
  "description" TEXT NOT NULL DEFAULT '',
  "client_pricing_model" "ServicePricingModel" NOT NULL,
  "manager_pricing_model" "ServicePricingModel" NOT NULL,
  "status" "OrganizationStatus" NOT NULL DEFAULT 'ACTIVE',
  "sort_order" INTEGER NOT NULL DEFAULT 0,
  "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TIMESTAMP(3) NOT NULL,
  CONSTRAINT "company_services_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "service_pricing" (
  "id" UUID NOT NULL,
  "company_id" UUID NOT NULL,
  "service_id" UUID NOT NULL,
  "scope" "ServicePricingScope" NOT NULL,
  "client_id" UUID,
  "manager_user_id" UUID,
  "pricing_model" "ServicePricingModel" NOT NULL,
  "amount" DECIMAL(12,2) NOT NULL,
  "currency" VARCHAR(3) NOT NULL DEFAULT 'INR',
  "notes" TEXT NOT NULL DEFAULT '',
  "effective_from" TIMESTAMP(3) NOT NULL,
  "effective_to" TIMESTAMP(3),
  "created_by_id" UUID NOT NULL,
  "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "service_pricing_pkey" PRIMARY KEY ("id"),
  CONSTRAINT "service_pricing_scope_subject_check" CHECK (
    (
      "scope" = 'CLIENT'::"ServicePricingScope"
      AND "client_id" IS NOT NULL
      AND "manager_user_id" IS NULL
    )
    OR (
      "scope" = 'MANAGER'::"ServicePricingScope"
      AND "manager_user_id" IS NOT NULL
      AND "client_id" IS NULL
    )
  )
);

-- CreateIndex
CREATE INDEX "company_services_company_id_status_sort_order_idx" ON "company_services"("company_id", "status", "sort_order");
CREATE INDEX "company_services_company_id_name_idx" ON "company_services"("company_id", "name");
CREATE UNIQUE INDEX "company_services_company_id_name_key" ON "company_services"("company_id", "name");
CREATE UNIQUE INDEX "company_services_company_id_code_key" ON "company_services"("company_id", "code");

CREATE INDEX "service_pricing_company_id_service_id_scope_effective_from_idx" ON "service_pricing"("company_id", "service_id", "scope", "effective_from");
CREATE INDEX "service_pricing_company_id_client_id_effective_from_idx" ON "service_pricing"("company_id", "client_id", "effective_from");
CREATE INDEX "service_pricing_company_id_manager_user_id_effective_from_idx" ON "service_pricing"("company_id", "manager_user_id", "effective_from");
CREATE INDEX "service_pricing_created_by_id_created_at_idx" ON "service_pricing"("created_by_id", "created_at");

CREATE UNIQUE INDEX "service_pricing_client_open_key"
ON "service_pricing"("company_id", "service_id", "client_id")
WHERE "scope" = 'CLIENT'::"ServicePricingScope" AND "effective_to" IS NULL;

CREATE UNIQUE INDEX "service_pricing_manager_open_key"
ON "service_pricing"("company_id", "service_id", "manager_user_id")
WHERE "scope" = 'MANAGER'::"ServicePricingScope" AND "effective_to" IS NULL;

-- AddForeignKey
ALTER TABLE "company_services"
ADD CONSTRAINT "company_services_company_id_fkey"
FOREIGN KEY ("company_id") REFERENCES "companies"("id") ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE "service_pricing"
ADD CONSTRAINT "service_pricing_company_id_fkey"
FOREIGN KEY ("company_id") REFERENCES "companies"("id") ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE "service_pricing"
ADD CONSTRAINT "service_pricing_service_id_fkey"
FOREIGN KEY ("service_id") REFERENCES "company_services"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE "service_pricing"
ADD CONSTRAINT "service_pricing_client_id_fkey"
FOREIGN KEY ("client_id") REFERENCES "clients"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE "service_pricing"
ADD CONSTRAINT "service_pricing_manager_user_id_fkey"
FOREIGN KEY ("manager_user_id") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE "service_pricing"
ADD CONSTRAINT "service_pricing_created_by_id_fkey"
FOREIGN KEY ("created_by_id") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- Seed default services for existing companies
INSERT INTO "company_services"(
  "id",
  "company_id",
  "name",
  "code",
  "description",
  "client_pricing_model",
  "manager_pricing_model",
  "status",
  "sort_order",
  "created_at",
  "updated_at"
)
SELECT
  gen_random_uuid(),
  c."id",
  seed."name",
  seed."code",
  seed."description",
  seed."client_pricing_model"::"ServicePricingModel",
  seed."manager_pricing_model"::"ServicePricingModel",
  'ACTIVE'::"OrganizationStatus",
  seed."sort_order",
  NOW(),
  NOW()
FROM "companies" c
CROSS JOIN (
  VALUES
    ('Reel', 'REEL', 'Short-form reel production service.', 'PER_VIDEO', 'COMMISSION_PER_DELIVERABLE', 10),
    ('Thumbnail', 'THUMBNAIL', 'Thumbnail design and export service.', 'PER_PIECE', 'COMMISSION_PER_DELIVERABLE', 20),
    ('Carousel', 'CAROUSEL', 'Carousel content design service.', 'PER_PIECE', 'COMMISSION_PER_DELIVERABLE', 30),
    ('Long Video', 'LONG_VIDEO', 'Long-form video editing and delivery service.', 'PER_VIDEO', 'COMMISSION_PER_DELIVERABLE', 40),
    ('SPLS Reel', 'SPLS_REEL', 'Specialized SPLS reel production service.', 'PER_VIDEO', 'COMMISSION_PER_DELIVERABLE', 50),
    ('Social Media Marketing', 'SOCIAL_MEDIA_MARKETING', 'Recurring social media marketing package.', 'MONTHLY_FIXED', 'COMMISSION_PER_DELIVERABLE', 60)
) AS seed("name", "code", "description", "client_pricing_model", "manager_pricing_model", "sort_order")
ON CONFLICT ("company_id", "code") DO NOTHING;
