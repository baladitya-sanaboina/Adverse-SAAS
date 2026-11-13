-- Color customization is intentionally deferred until every application surface
-- consumes one shared semantic design system. Keep stored tenant palettes on the
-- stable Adverse baseline in the meantime.
UPDATE "company_tenant_defaults"
SET
  "primary_color" = '#0876ED',
  "secondary_color" = '#065EC1',
  "accent_color" = '#3D9BF5',
  "info_color" = '#2563A6',
  "success_color" = '#16855B',
  "warning_color" = '#B7791F',
  "danger_color" = '#C2414F',
  "updated_at" = NOW();
