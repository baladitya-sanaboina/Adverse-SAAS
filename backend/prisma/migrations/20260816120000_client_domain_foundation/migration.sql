CREATE TABLE "clients" (
    "id" UUID NOT NULL,
    "company_id" UUID NOT NULL,
    "name" TEXT NOT NULL,
    "code" TEXT NOT NULL,
    "email" TEXT,
    "phone" TEXT,
    "website" TEXT,
    "address" TEXT NOT NULL DEFAULT '',
    "city" TEXT NOT NULL DEFAULT '',
    "state" TEXT NOT NULL DEFAULT '',
    "country" TEXT NOT NULL DEFAULT '',
    "status" "OrganizationStatus" NOT NULL DEFAULT 'ACTIVE',
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "clients_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "client_contacts" (
    "id" UUID NOT NULL,
    "client_id" UUID NOT NULL,
    "first_name" TEXT NOT NULL,
    "last_name" TEXT NOT NULL DEFAULT '',
    "email" TEXT,
    "phone" TEXT,
    "designation" TEXT NOT NULL DEFAULT '',
    "is_primary" BOOLEAN NOT NULL DEFAULT false,
    "status" "OrganizationStatus" NOT NULL DEFAULT 'ACTIVE',
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "client_contacts_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "clients_company_id_code_key" ON "clients"("company_id", "code");
CREATE INDEX "clients_company_id_status_idx" ON "clients"("company_id", "status");
CREATE INDEX "clients_company_id_name_idx" ON "clients"("company_id", "name");

CREATE UNIQUE INDEX "client_contacts_client_id_email_key"
ON "client_contacts"("client_id", "email");
CREATE INDEX "client_contacts_client_id_status_idx"
ON "client_contacts"("client_id", "status");
CREATE INDEX "client_contacts_client_id_is_primary_idx"
ON "client_contacts"("client_id", "is_primary");

ALTER TABLE "clients"
ADD CONSTRAINT "clients_company_id_fkey"
FOREIGN KEY ("company_id") REFERENCES "companies"("id") ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE "client_contacts"
ADD CONSTRAINT "client_contacts_client_id_fkey"
FOREIGN KEY ("client_id") REFERENCES "clients"("id") ON DELETE CASCADE ON UPDATE CASCADE;
