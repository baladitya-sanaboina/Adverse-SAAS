-- CreateEnum
CREATE TYPE "TaskStatus" AS ENUM ('PENDING', 'ASSIGNED', 'IN_PROGRESS', 'SUBMITTED', 'REVIEW', 'APPROVED', 'COMPLETED', 'CANCELLED');

-- CreateEnum
CREATE TYPE "TaskPriority" AS ENUM ('LOW', 'MEDIUM', 'HIGH', 'URGENT');

-- CreateEnum
CREATE TYPE "TaskAssigneeType" AS ENUM ('MANAGER', 'EMPLOYEE');

-- CreateEnum
CREATE TYPE "TaskFileKind" AS ENUM ('REFERENCE', 'DELIVERABLE');

-- CreateEnum
CREATE TYPE "TaskPriceField" AS ENUM ('CLIENT_PRICE', 'COMMISSION');

-- CreateEnum
CREATE TYPE "ClientBudgetEntryType" AS ENUM ('INITIAL', 'TOP_UP', 'ADJUSTMENT');

-- CreateEnum
CREATE TYPE "PaymentMethod" AS ENUM ('CASH', 'BANK_TRANSFER', 'UPI', 'CHEQUE', 'CARD', 'OTHER');

-- CreateTable
CREATE TABLE "tasks" (
    "id" UUID NOT NULL,
    "company_id" UUID NOT NULL,
    "number" INTEGER NOT NULL,
    "client_id" UUID NOT NULL,
    "service_id" UUID NOT NULL,
    "title" TEXT NOT NULL,
    "description" TEXT NOT NULL DEFAULT '',
    "priority" "TaskPriority" NOT NULL DEFAULT 'MEDIUM',
    "status" "TaskStatus" NOT NULL DEFAULT 'PENDING',
    "assignee_user_id" UUID,
    "assignee_type" "TaskAssigneeType",
    "monitor_user_id" UUID,
    "due_date" DATE,
    "currency" VARCHAR(3) NOT NULL DEFAULT 'INR',
    "client_pricing_model" "ServicePricingModel" NOT NULL,
    "client_price_default" DECIMAL(12,2),
    "client_price_final" DECIMAL(12,2) NOT NULL,
    "client_price_reason" TEXT NOT NULL DEFAULT '',
    "commission_default" DECIMAL(12,2),
    "commission_final" DECIMAL(12,2),
    "commission_reason" TEXT NOT NULL DEFAULT '',
    "created_by_id" UUID NOT NULL,
    "assigned_at" TIMESTAMP(3),
    "started_at" TIMESTAMP(3),
    "submitted_at" TIMESTAMP(3),
    "approved_at" TIMESTAMP(3),
    "completed_at" TIMESTAMP(3),
    "cancelled_at" TIMESTAMP(3),
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "tasks_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "task_status_history" (
    "id" UUID NOT NULL,
    "company_id" UUID NOT NULL,
    "task_id" UUID NOT NULL,
    "from_status" "TaskStatus",
    "to_status" "TaskStatus" NOT NULL,
    "actor_id" UUID NOT NULL,
    "note" TEXT NOT NULL DEFAULT '',
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "task_status_history_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "task_price_changes" (
    "id" UUID NOT NULL,
    "company_id" UUID NOT NULL,
    "task_id" UUID NOT NULL,
    "field" "TaskPriceField" NOT NULL,
    "old_amount" DECIMAL(12,2),
    "new_amount" DECIMAL(12,2),
    "reason" TEXT NOT NULL DEFAULT '',
    "actor_id" UUID NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "task_price_changes_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "task_comments" (
    "id" UUID NOT NULL,
    "company_id" UUID NOT NULL,
    "task_id" UUID NOT NULL,
    "author_id" UUID NOT NULL,
    "content" TEXT NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "task_comments_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "task_files" (
    "id" UUID NOT NULL,
    "company_id" UUID NOT NULL,
    "task_id" UUID NOT NULL,
    "kind" "TaskFileKind" NOT NULL,
    "file_name" TEXT NOT NULL,
    "storage_path" TEXT NOT NULL,
    "mime_type" TEXT NOT NULL,
    "size_bytes" BIGINT NOT NULL,
    "uploaded_by_id" UUID NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "task_files_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "client_budget_entries" (
    "id" UUID NOT NULL,
    "company_id" UUID NOT NULL,
    "client_id" UUID NOT NULL,
    "type" "ClientBudgetEntryType" NOT NULL,
    "amount" DECIMAL(12,2) NOT NULL,
    "currency" VARCHAR(3) NOT NULL DEFAULT 'INR',
    "note" TEXT NOT NULL DEFAULT '',
    "created_by_id" UUID NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "client_budget_entries_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "client_payments" (
    "id" UUID NOT NULL,
    "company_id" UUID NOT NULL,
    "client_id" UUID NOT NULL,
    "amount" DECIMAL(12,2) NOT NULL,
    "currency" VARCHAR(3) NOT NULL DEFAULT 'INR',
    "received_on" DATE NOT NULL,
    "method" "PaymentMethod" NOT NULL DEFAULT 'BANK_TRANSFER',
    "reference" TEXT NOT NULL DEFAULT '',
    "note" TEXT NOT NULL DEFAULT '',
    "created_by_id" UUID NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "client_payments_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "employee_salaries" (
    "id" UUID NOT NULL,
    "company_id" UUID NOT NULL,
    "user_id" UUID NOT NULL,
    "monthly_amount" DECIMAL(12,2) NOT NULL,
    "currency" VARCHAR(3) NOT NULL DEFAULT 'INR',
    "effective_from" DATE NOT NULL,
    "effective_to" DATE,
    "note" TEXT NOT NULL DEFAULT '',
    "created_by_id" UUID NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "employee_salaries_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "salary_payments" (
    "id" UUID NOT NULL,
    "company_id" UUID NOT NULL,
    "user_id" UUID NOT NULL,
    "period_month" DATE NOT NULL,
    "amount" DECIMAL(12,2) NOT NULL,
    "currency" VARCHAR(3) NOT NULL DEFAULT 'INR',
    "paid_on" DATE NOT NULL,
    "method" "PaymentMethod" NOT NULL DEFAULT 'BANK_TRANSFER',
    "reference" TEXT NOT NULL DEFAULT '',
    "note" TEXT NOT NULL DEFAULT '',
    "created_by_id" UUID NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "salary_payments_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "manager_payouts" (
    "id" UUID NOT NULL,
    "company_id" UUID NOT NULL,
    "manager_user_id" UUID NOT NULL,
    "amount" DECIMAL(12,2) NOT NULL,
    "currency" VARCHAR(3) NOT NULL DEFAULT 'INR',
    "paid_on" DATE NOT NULL,
    "method" "PaymentMethod" NOT NULL DEFAULT 'BANK_TRANSFER',
    "reference" TEXT NOT NULL DEFAULT '',
    "note" TEXT NOT NULL DEFAULT '',
    "created_by_id" UUID NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "manager_payouts_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "tasks_company_id_status_due_date_idx" ON "tasks"("company_id", "status", "due_date");

-- CreateIndex
CREATE INDEX "tasks_company_id_client_id_status_idx" ON "tasks"("company_id", "client_id", "status");

-- CreateIndex
CREATE INDEX "tasks_company_id_service_id_status_idx" ON "tasks"("company_id", "service_id", "status");

-- CreateIndex
CREATE INDEX "tasks_company_id_assignee_user_id_status_idx" ON "tasks"("company_id", "assignee_user_id", "status");

-- CreateIndex
CREATE INDEX "tasks_company_id_monitor_user_id_status_idx" ON "tasks"("company_id", "monitor_user_id", "status");

-- CreateIndex
CREATE INDEX "tasks_company_id_approved_at_idx" ON "tasks"("company_id", "approved_at");

-- CreateIndex
CREATE UNIQUE INDEX "tasks_company_id_number_key" ON "tasks"("company_id", "number");

-- CreateIndex
CREATE INDEX "task_status_history_task_id_created_at_idx" ON "task_status_history"("task_id", "created_at");

-- CreateIndex
CREATE INDEX "task_status_history_company_id_created_at_idx" ON "task_status_history"("company_id", "created_at");

-- CreateIndex
CREATE INDEX "task_price_changes_task_id_created_at_idx" ON "task_price_changes"("task_id", "created_at");

-- CreateIndex
CREATE INDEX "task_comments_task_id_created_at_idx" ON "task_comments"("task_id", "created_at");

-- CreateIndex
CREATE UNIQUE INDEX "task_files_storage_path_key" ON "task_files"("storage_path");

-- CreateIndex
CREATE INDEX "task_files_task_id_kind_created_at_idx" ON "task_files"("task_id", "kind", "created_at");

-- CreateIndex
CREATE INDEX "client_budget_entries_company_id_client_id_created_at_idx" ON "client_budget_entries"("company_id", "client_id", "created_at");

-- CreateIndex
CREATE INDEX "client_payments_company_id_client_id_received_on_idx" ON "client_payments"("company_id", "client_id", "received_on");

-- CreateIndex
CREATE INDEX "client_payments_company_id_received_on_idx" ON "client_payments"("company_id", "received_on");

-- CreateIndex
CREATE INDEX "employee_salaries_company_id_user_id_effective_from_idx" ON "employee_salaries"("company_id", "user_id", "effective_from");

-- CreateIndex
CREATE INDEX "salary_payments_company_id_user_id_period_month_idx" ON "salary_payments"("company_id", "user_id", "period_month");

-- CreateIndex
CREATE INDEX "salary_payments_company_id_paid_on_idx" ON "salary_payments"("company_id", "paid_on");

-- CreateIndex
CREATE INDEX "manager_payouts_company_id_manager_user_id_paid_on_idx" ON "manager_payouts"("company_id", "manager_user_id", "paid_on");

-- CreateIndex
CREATE INDEX "manager_payouts_company_id_paid_on_idx" ON "manager_payouts"("company_id", "paid_on");

-- AddForeignKey
ALTER TABLE "tasks" ADD CONSTRAINT "tasks_company_id_fkey" FOREIGN KEY ("company_id") REFERENCES "companies"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "tasks" ADD CONSTRAINT "tasks_client_id_fkey" FOREIGN KEY ("client_id") REFERENCES "clients"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "tasks" ADD CONSTRAINT "tasks_service_id_fkey" FOREIGN KEY ("service_id") REFERENCES "company_services"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "tasks" ADD CONSTRAINT "tasks_assignee_user_id_fkey" FOREIGN KEY ("assignee_user_id") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "tasks" ADD CONSTRAINT "tasks_monitor_user_id_fkey" FOREIGN KEY ("monitor_user_id") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "tasks" ADD CONSTRAINT "tasks_created_by_id_fkey" FOREIGN KEY ("created_by_id") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "task_status_history" ADD CONSTRAINT "task_status_history_company_id_fkey" FOREIGN KEY ("company_id") REFERENCES "companies"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "task_status_history" ADD CONSTRAINT "task_status_history_task_id_fkey" FOREIGN KEY ("task_id") REFERENCES "tasks"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "task_status_history" ADD CONSTRAINT "task_status_history_actor_id_fkey" FOREIGN KEY ("actor_id") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "task_price_changes" ADD CONSTRAINT "task_price_changes_company_id_fkey" FOREIGN KEY ("company_id") REFERENCES "companies"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "task_price_changes" ADD CONSTRAINT "task_price_changes_task_id_fkey" FOREIGN KEY ("task_id") REFERENCES "tasks"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "task_price_changes" ADD CONSTRAINT "task_price_changes_actor_id_fkey" FOREIGN KEY ("actor_id") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "task_comments" ADD CONSTRAINT "task_comments_company_id_fkey" FOREIGN KEY ("company_id") REFERENCES "companies"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "task_comments" ADD CONSTRAINT "task_comments_task_id_fkey" FOREIGN KEY ("task_id") REFERENCES "tasks"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "task_comments" ADD CONSTRAINT "task_comments_author_id_fkey" FOREIGN KEY ("author_id") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "task_files" ADD CONSTRAINT "task_files_company_id_fkey" FOREIGN KEY ("company_id") REFERENCES "companies"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "task_files" ADD CONSTRAINT "task_files_task_id_fkey" FOREIGN KEY ("task_id") REFERENCES "tasks"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "task_files" ADD CONSTRAINT "task_files_uploaded_by_id_fkey" FOREIGN KEY ("uploaded_by_id") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "client_budget_entries" ADD CONSTRAINT "client_budget_entries_company_id_fkey" FOREIGN KEY ("company_id") REFERENCES "companies"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "client_budget_entries" ADD CONSTRAINT "client_budget_entries_client_id_fkey" FOREIGN KEY ("client_id") REFERENCES "clients"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "client_budget_entries" ADD CONSTRAINT "client_budget_entries_created_by_id_fkey" FOREIGN KEY ("created_by_id") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "client_payments" ADD CONSTRAINT "client_payments_company_id_fkey" FOREIGN KEY ("company_id") REFERENCES "companies"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "client_payments" ADD CONSTRAINT "client_payments_client_id_fkey" FOREIGN KEY ("client_id") REFERENCES "clients"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "client_payments" ADD CONSTRAINT "client_payments_created_by_id_fkey" FOREIGN KEY ("created_by_id") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "employee_salaries" ADD CONSTRAINT "employee_salaries_company_id_fkey" FOREIGN KEY ("company_id") REFERENCES "companies"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "employee_salaries" ADD CONSTRAINT "employee_salaries_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "employee_salaries" ADD CONSTRAINT "employee_salaries_created_by_id_fkey" FOREIGN KEY ("created_by_id") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "salary_payments" ADD CONSTRAINT "salary_payments_company_id_fkey" FOREIGN KEY ("company_id") REFERENCES "companies"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "salary_payments" ADD CONSTRAINT "salary_payments_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "salary_payments" ADD CONSTRAINT "salary_payments_created_by_id_fkey" FOREIGN KEY ("created_by_id") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "manager_payouts" ADD CONSTRAINT "manager_payouts_company_id_fkey" FOREIGN KEY ("company_id") REFERENCES "companies"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "manager_payouts" ADD CONSTRAINT "manager_payouts_manager_user_id_fkey" FOREIGN KEY ("manager_user_id") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "manager_payouts" ADD CONSTRAINT "manager_payouts_created_by_id_fkey" FOREIGN KEY ("created_by_id") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;


-- ---------------------------------------------------------------------------
-- Data-safety rules (docs/ProductionManagementPlan.md, sections 3 and 6)
-- ---------------------------------------------------------------------------

-- Tasks: an assignee always has a type; commission exists only for managers; no negative money.
ALTER TABLE "tasks" ADD CONSTRAINT "tasks_assignee_pair_check"
CHECK (("assignee_user_id" IS NULL) = ("assignee_type" IS NULL));

ALTER TABLE "tasks" ADD CONSTRAINT "tasks_commission_manager_only_check"
CHECK (
  "assignee_type" = 'MANAGER'::"TaskAssigneeType"
  OR ("commission_default" IS NULL AND "commission_final" IS NULL)
);

ALTER TABLE "tasks" ADD CONSTRAINT "tasks_non_negative_amounts_check"
CHECK (
  "client_price_final" >= 0
  AND ("client_price_default" IS NULL OR "client_price_default" >= 0)
  AND ("commission_default" IS NULL OR "commission_default" >= 0)
  AND ("commission_final" IS NULL OR "commission_final" >= 0)
);

ALTER TABLE "tasks" ADD CONSTRAINT "tasks_number_positive_check" CHECK ("number" > 0);

-- Budgets: initial amounts and top-ups add money; only adjustments may be negative.
ALTER TABLE "client_budget_entries" ADD CONSTRAINT "client_budget_entries_amount_check"
CHECK ("type" = 'ADJUSTMENT'::"ClientBudgetEntryType" OR "amount" > 0);

-- Payments and salaries are positive amounts.
ALTER TABLE "client_payments" ADD CONSTRAINT "client_payments_amount_check" CHECK ("amount" > 0);
ALTER TABLE "salary_payments" ADD CONSTRAINT "salary_payments_amount_check" CHECK ("amount" > 0);
ALTER TABLE "manager_payouts" ADD CONSTRAINT "manager_payouts_amount_check" CHECK ("amount" > 0);
ALTER TABLE "employee_salaries" ADD CONSTRAINT "employee_salaries_amount_check" CHECK ("monthly_amount" >= 0);

-- Salary periods are stored as the first day of the month.
ALTER TABLE "salary_payments" ADD CONSTRAINT "salary_payments_period_month_check"
CHECK ("period_month" = date_trunc('month', "period_month")::date);

-- Salary history: effective ranges are valid, and each person has at most one open salary.
ALTER TABLE "employee_salaries" ADD CONSTRAINT "employee_salaries_range_check"
CHECK ("effective_to" IS NULL OR "effective_to" >= "effective_from");

CREATE UNIQUE INDEX "employee_salaries_open_key"
ON "employee_salaries"("company_id", "user_id")
WHERE "effective_to" IS NULL;
