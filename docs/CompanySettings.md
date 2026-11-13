# Company Settings

## Scope

Day-28 adds tenant-scoped configuration for the current company. Day-37 extends the same authoritative company entity and settings interface with company description, explicit logo/favicon removal, live visual preview, and unsaved-change controls. It does not create a duplicate company profile model or separate branding store.

## Authorization and tenant isolation

- Only an authenticated `COMPANY_ADMIN` can read or update administrative company settings.
- The target company is derived from the validated JWT `company_id`; clients cannot select another company through a header, path, or request body.
- Company Employee and Company Client can read only the safe visual-branding projection for their own authenticated tenant. Platform Owner, Developer, anonymous, invalid, and expired sessions are rejected.
- Company-level values never modify `platform_settings` or another tenant.

## API

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/company/settings` | Return current tenant configuration |
| `GET` | `/company/branding` | Return current tenant name, logo and palette to company-role workspaces |
| `PUT` | `/company/settings` | Atomically update all company setting groups |
| `PUT` | `/company/settings/preferences` | Update preferences and notifications |
| `POST` | `/company/settings/branding/{logo\|favicon}` | Upload a tenant branding image |
| `DELETE` | `/company/settings/branding/{logo\|favicon}` | Remove a tenant branding image and restore the default identity |

Swagger documents request, response, validation, authorization, conflict, and not-found responses. Version `0.28.0` includes the Day-37 profile and branding behavior.

## Storage and validation

Company name, description, contact, and regional fundamentals are stored on `companies`; branding, legal identifiers, locale formats, notifications, working days, business hours, and theme defaults are stored in `company_tenant_defaults`. Images are isolated under `storage/company-branding/{company_id}`. Only verified PNG, JPEG, and WebP content up to 2 MB is accepted.

The semantic palette fields are reserved for a future unified design-system release. Color customization is currently displayed as **Coming soon** and is not applied to Company Admin, Employee, or Client workspaces; all three continue to use the stable Loopless palette. Logo and favicon branding remain active, tenant-scoped, and uploaded artwork is never modified with CSS colour filters.

Company name and business email uniqueness are database-enforced. Colors use six-digit hex values, currency uses an ISO-style three-letter code, locale formats use supported values, working days must be unique, and business closing time must be later than opening time.

## Audit events

Updates store the actor, company, timestamp, and changed field names in `company_setting_audits`. Events include:

- `COMPANY_SETTINGS_UPDATED`
- `COMPANY_BRANDING_UPDATED`
- `COMPANY_CONTACT_UPDATED`
- `COMPANY_REGIONAL_UPDATED`
- `COMPANY_NOTIFICATION_PREFERENCES_UPDATED`
- `COMPANY_PREFERENCES_UPDATED`
- `COMPANY_LOGO_UPDATED`
- `COMPANY_FAVICON_UPDATED`

## Migration

Apply migrations with `docker compose -f docker/docker-compose.yml run --rm migrations`. Migration `20260806110000_add_company_settings` extends tenant defaults, backfills any existing company missing a defaults row, and creates the audit table without deleting existing tenant data. Day-37 migration `20260810120000_company_profile_branding` adds the optional authoritative company description. Migration `20260810121500_company_semantic_brand_palette` reserves semantic palette storage, while `20260810123000_defer_company_color_customization` restores every tenant to the stable Loopless baseline until the complete design system is ready.
