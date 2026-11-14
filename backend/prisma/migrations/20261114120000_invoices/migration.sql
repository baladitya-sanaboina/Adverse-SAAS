-- CreateEnum
CREATE TYPE "InvoiceStatus" AS ENUM ('DRAFT', 'SENT', 'PAID', 'VOID');

-- CreateTable
CREATE TABLE "invoices" (
    "id" UUID NOT NULL,
    "company_id" UUID NOT NULL,
    "client_id" UUID NOT NULL,
    "number" INTEGER NOT NULL,
    "status" "InvoiceStatus" NOT NULL DEFAULT 'DRAFT',
    "source" VARCHAR(20) NOT NULL DEFAULT 'MANUAL',
    "period_start" DATE NOT NULL,
    "period_end" DATE NOT NULL,
    "issue_date" DATE NOT NULL,
    "due_date" DATE,
    "currency" VARCHAR(3) NOT NULL,
    "subtotal" DECIMAL(12,2) NOT NULL,
    "payments_total" DECIMAL(12,2) NOT NULL,
    "budget_added" DECIMAL(12,2) NOT NULL,
    "payments" JSONB NOT NULL DEFAULT '[]',
    "notes" VARCHAR(1000) NOT NULL DEFAULT '',
    "created_by_id" UUID NOT NULL,
    "sent_at" TIMESTAMP(3),
    "paid_at" TIMESTAMP(3),
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "invoices_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "invoice_lines" (
    "id" UUID NOT NULL,
    "invoice_id" UUID NOT NULL,
    "task_id" UUID,
    "position" INTEGER NOT NULL,
    "delivered_on" DATE NOT NULL,
    "title" VARCHAR(200) NOT NULL,
    "service_name" VARCHAR(120) NOT NULL,
    "amount" DECIMAL(12,2) NOT NULL,

    CONSTRAINT "invoice_lines_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "invoices_company_id_client_id_created_at_idx" ON "invoices"("company_id", "client_id", "created_at");

-- CreateIndex
CREATE UNIQUE INDEX "invoices_company_id_number_key" ON "invoices"("company_id", "number");

-- CreateIndex
CREATE INDEX "invoice_lines_invoice_id_position_idx" ON "invoice_lines"("invoice_id", "position");

-- AddForeignKey
ALTER TABLE "invoices" ADD CONSTRAINT "invoices_company_id_fkey" FOREIGN KEY ("company_id") REFERENCES "companies"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "invoices" ADD CONSTRAINT "invoices_client_id_fkey" FOREIGN KEY ("client_id") REFERENCES "clients"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "invoices" ADD CONSTRAINT "invoices_created_by_id_fkey" FOREIGN KEY ("created_by_id") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "invoice_lines" ADD CONSTRAINT "invoice_lines_invoice_id_fkey" FOREIGN KEY ("invoice_id") REFERENCES "invoices"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "invoice_lines" ADD CONSTRAINT "invoice_lines_task_id_fkey" FOREIGN KEY ("task_id") REFERENCES "tasks"("id") ON DELETE SET NULL ON UPDATE CASCADE;


-- Guards (same style as the production_management migration)
ALTER TABLE "invoices" ADD CONSTRAINT "invoices_amounts_not_negative" CHECK ("subtotal" >= 0 AND "payments_total" >= 0 AND "budget_added" >= 0);
ALTER TABLE "invoices" ADD CONSTRAINT "invoices_period_order" CHECK ("period_end" >= "period_start");
ALTER TABLE "invoice_lines" ADD CONSTRAINT "invoice_lines_amount_not_negative" CHECK ("amount" >= 0);
