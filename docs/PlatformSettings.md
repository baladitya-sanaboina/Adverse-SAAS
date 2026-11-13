# Platform Settings

Day-26 adds one global settings record managed only by the Platform Owner. These settings are platform-wide; they are not tenant white-label settings.

## Configuration areas

- General: platform name, support contact, footer text.
- Branding: logo, favicon, primary and secondary colors.
- SMTP: host, port, encryption, credentials, sender identity, and test delivery.
- Maintenance: enabled state, public message, and Developer access allowance. Platform Owner access is always retained.
- Defaults: company/user status, subscription code, timezone, and language used by future onboarding flows.

## APIs

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/platform/settings` | Read the complete masked configuration |
| PUT | `/platform/settings` | Update general configuration and defaults |
| PUT | `/platform/settings/smtp` | Update SMTP configuration |
| POST | `/platform/settings/test-email` | Send a branded SMTP test email |
| PUT | `/platform/settings/maintenance` | Enable, disable, or configure maintenance |
| GET | `/platform/settings/maintenance/status` | Read the public maintenance state |
| POST | `/platform/settings/branding/{asset}` | Upload `logo` or `favicon` |

## Security

Protected endpoints require a valid Platform Owner access token. SMTP passwords are encrypted at rest, are never returned by the API, and can only be replaced. Branding uploads accept PNG, JPEG, WebP, and ICO up to 2 MB. Platform Owner is always allowed during maintenance; company roles receive `503 MAINTENANCE_MODE`, while Developers are allowed only when configured.

## Audit trail

Every settings, SMTP, maintenance, logo, favicon, and test-email action records the actor, timestamp, changed fields, and previous/new values where applicable. Plaintext SMTP passwords are never written to audit data.

## Development SMTP test

Use Mailpit at `http://localhost:8025`. Configure host `mailpit`, port `1025`, encryption `NONE`, then send a test from the SMTP tab. In CI, Mailpit readiness and SMTP reachability are checked independently of external mail providers.

## Migration

Run `npx prisma migrate deploy` in the backend environment. The migration creates `platform_settings` as a singleton row and `platform_setting_audits` for the immutable audit history.
