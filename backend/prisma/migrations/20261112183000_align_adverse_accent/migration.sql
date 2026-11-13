-- Align all tenant accent colours with the Adverse brand system and remove the
-- leftover legacy purple default used by earlier Loopless-era seed data.
ALTER TABLE "company_tenant_defaults"
  ALTER COLUMN "accent_color" SET DEFAULT '#0876ED';

UPDATE "company_tenant_defaults"
SET
  "accent_color" = '#0876ED',
  "updated_at" = NOW()
WHERE UPPER("accent_color") IN ('#8B6AAF', '#715795', '#3D9BF5');
