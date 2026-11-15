-- Invoice numbers ADV-0001, GST per client, monthly packages (owner requests 2026-11-15).

-- Invoices: a number prefix (invoices already sent keep their INV prefix), GST snapshot.
ALTER TABLE "invoices" ADD COLUMN "prefix" VARCHAR(8) NOT NULL DEFAULT 'ADV';
UPDATE "invoices" SET "prefix" = 'INV';
ALTER TABLE "invoices" ADD COLUMN "tax_rate" DECIMAL(5,2) NOT NULL DEFAULT 0;
ALTER TABLE "invoices" ADD COLUMN "tax_amount" DECIMAL(12,2) NOT NULL DEFAULT 0;
ALTER TABLE "invoices" ADD COLUMN "client_gstin" VARCHAR(20) NOT NULL DEFAULT '';
ALTER TABLE "invoices" ADD CONSTRAINT "invoices_tax_check" CHECK ("tax_rate" >= 0 AND "tax_rate" <= 100 AND "tax_amount" >= 0);

-- GST per client: off by default; 18% when switched on.
ALTER TABLE "clients" ADD COLUMN "gst_enabled" BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE "clients" ADD COLUMN "gst_rate" DECIMAL(5,2) NOT NULL DEFAULT 18;
ALTER TABLE "clients" ADD COLUMN "gstin" VARCHAR(20) NOT NULL DEFAULT '';
ALTER TABLE "clients" ADD CONSTRAINT "clients_gst_rate_check" CHECK ("gst_rate" >= 0 AND "gst_rate" <= 100);

-- Monthly packages: a fixed monthly price covers a number of videos; extra videos are billed
-- at the client's per-item rate. A package is never edited in place, it is ended and replaced,
-- so months already charged keep their price.
CREATE TABLE "client_packages" (
    "id" UUID NOT NULL,
    "company_id" UUID NOT NULL,
    "client_id" UUID NOT NULL,
    "name" VARCHAR(120) NOT NULL,
    "monthly_price" DECIMAL(12,2) NOT NULL,
    "videos_included" INTEGER NOT NULL,
    "starts_on" DATE NOT NULL,
    "ends_on" DATE,
    "created_by_id" UUID NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "client_packages_pkey" PRIMARY KEY ("id"),
    CONSTRAINT "client_packages_amounts_check" CHECK ("monthly_price" >= 0 AND "videos_included" >= 0),
    CONSTRAINT "client_packages_dates_check" CHECK ("ends_on" IS NULL OR "ends_on" >= "starts_on")
);

CREATE INDEX "client_packages_company_id_client_id_starts_on_idx" ON "client_packages"("company_id", "client_id", "starts_on");

ALTER TABLE "client_packages" ADD CONSTRAINT "client_packages_company_id_fkey" FOREIGN KEY ("company_id") REFERENCES "companies"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "client_packages" ADD CONSTRAINT "client_packages_client_id_fkey" FOREIGN KEY ("client_id") REFERENCES "clients"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
ALTER TABLE "client_packages" ADD CONSTRAINT "client_packages_created_by_id_fkey" FOREIGN KEY ("created_by_id") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- A video covered by a package (its price was set to 0 when it was approved).
ALTER TABLE "tasks" ADD COLUMN "package_id" UUID;
ALTER TABLE "tasks" ADD CONSTRAINT "tasks_package_id_fkey" FOREIGN KEY ("package_id") REFERENCES "client_packages"("id") ON DELETE SET NULL ON UPDATE CASCADE;
CREATE INDEX "tasks_package_id_idx" ON "tasks"("package_id");
