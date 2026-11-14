-- Content calendar (Phase 13). Purely additive: one new table, no existing table changed.

-- CreateTable
CREATE TABLE "content_calendar_entries" (
    "id" UUID NOT NULL,
    "company_id" UUID NOT NULL,
    "client_id" UUID NOT NULL,
    "entry_date" DATE NOT NULL,
    "title" VARCHAR(200) NOT NULL,
    "reference_url" VARCHAR(1000) NOT NULL DEFAULT '',
    "notes" VARCHAR(2000) NOT NULL DEFAULT '',
    "no_post" BOOLEAN NOT NULL DEFAULT false,
    "recorded" BOOLEAN NOT NULL DEFAULT false,
    "script_ready" BOOLEAN NOT NULL DEFAULT false,
    "posted_instagram" BOOLEAN NOT NULL DEFAULT false,
    "posted_youtube" BOOLEAN NOT NULL DEFAULT false,
    "edited_manual" BOOLEAN NOT NULL DEFAULT false,
    "script_file_name" VARCHAR(200),
    "script_storage_path" VARCHAR(500),
    "script_mime_type" VARCHAR(200),
    "script_size_bytes" BIGINT,
    "task_id" UUID,
    "created_by_id" UUID NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "content_calendar_entries_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "content_calendar_entries_company_id_entry_date_idx" ON "content_calendar_entries"("company_id", "entry_date");

-- CreateIndex
CREATE INDEX "content_calendar_entries_company_id_client_id_entry_date_idx" ON "content_calendar_entries"("company_id", "client_id", "entry_date");

-- CreateIndex
CREATE INDEX "content_calendar_entries_task_id_idx" ON "content_calendar_entries"("task_id");

-- AddForeignKey
ALTER TABLE "content_calendar_entries" ADD CONSTRAINT "content_calendar_entries_company_id_fkey" FOREIGN KEY ("company_id") REFERENCES "companies"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "content_calendar_entries" ADD CONSTRAINT "content_calendar_entries_client_id_fkey" FOREIGN KEY ("client_id") REFERENCES "clients"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "content_calendar_entries" ADD CONSTRAINT "content_calendar_entries_task_id_fkey" FOREIGN KEY ("task_id") REFERENCES "tasks"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "content_calendar_entries" ADD CONSTRAINT "content_calendar_entries_created_by_id_fkey" FOREIGN KEY ("created_by_id") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
