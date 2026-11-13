# Company Onboarding

Day-27 introduces the guided company onboarding foundation. Platform Owners and Developers with the required `COMPANIES` permission can create a complete tenant workspace through one reviewed request.

## Wizard

The Companies workspace contains four steps:

1. Company information: identity, business contact, address, website, timezone, and language.
2. Subscription plan: one active plan and its feature/limit configuration.
3. Company Admin: first administrator identity and secure initial password.
4. Review and finish: read-only confirmation before setup.

Back and Continue preserve entered data. Validation is shown inline before a step advances. Submission has a locked loading state so duplicate onboarding requests cannot be sent.

## APIs

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/platform/onboarding` | Create the company workspace and onboarding record |
| GET | `/platform/onboarding/{companyId}` | Read the complete onboarding summary and audit trail |

Both APIs require JWT authentication and request-time `COMPANIES_CREATE` or `COMPANIES_VIEW` authorization. Platform Owner uses the documented RBAC bypass; authorized Developers use assigned permissions. Invalid UUIDs return `422`, missing plans/onboardings return `404`, and duplicate company name/code/business email/admin email values return `409`.

## Transaction boundary

One database transaction creates:

- the initially pending Company, then activates it after database initialization;
- the active Company Subscription and empty usage counters;
- the `PENDING_VERIFICATION` Company Admin with `COMPANY_ADMIN` role;
- copied platform branding, timezone, language, role/permission source, notification preferences, and dashboard defaults;
- onboarding progress and immutable audit events.

Any database initialization failure rolls back the complete database unit. Email delivery deliberately runs after commit so an external SMTP success cannot be followed by a rolled-back company. Delivery is tracked as `PENDING`, `SENT`, or `FAILED`; a failed email leaves an auditable `EMAIL_FAILED` onboarding that can be retried in a later mail-queue milestone.

## Email security

On success, Mailpit receives a branded workspace welcome email and the normal single-use verification email. The welcome email includes company/login context but never contains the submitted plaintext password. The administrator must verify the email before login.

## Status and audit events

Progress exposes company creation, subscription assignment, administrator creation, tenant initialization, copied defaults, and welcome-email delivery. The audit trail records:

- `ONBOARDING_STARTED`
- `COMPANY_CREATED`
- `SUBSCRIPTION_ASSIGNED`
- `COMPANY_ADMIN_CREATED`
- `WELCOME_EMAIL_SENT` or `WELCOME_EMAIL_FAILED`
- `ONBOARDING_COMPLETED`

## Migration

Run `npx prisma migrate deploy` in the backend environment. Day-27 adds company contact/localization fields, onboarding progress, tenant defaults, onboarding audits, and unique company names. No Company Settings or Department implementation is included.
