-- Owner decision 2026-11-15: the company works in Indian rupees; new companies default to INR.
ALTER TABLE "company_tenant_defaults" ALTER COLUMN "currency" SET DEFAULT 'INR';
