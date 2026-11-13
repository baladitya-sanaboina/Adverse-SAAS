# Company Admin Checkpoint

## Scope

Day-40 closes the Company Admin and Internal Setup phase. It validates the features delivered from Day-31 through Day-39 without introducing Employee, Attendance, Leave, CRM, Client, or Project-management functionality.

## Verified baseline

Validation performed on 2026-08-10 against API version `0.30.0` and migration `20260810131500_company_admin_settings_permissions`.

- Backend formatting, linting, typing, and all 123 automated tests pass.
- All five frontend applications pass type-check, lint, and production build.
- Platform Owner, Developer, Company Admin, Company Employee, and Company Client respond on ports 3000–3004.
- Backend, PostgreSQL, Redis, and Mailpit report healthy.
- Swagger exposes 90 operations, including all Company Admin dashboard, organization, invitation, assignment, role, settings, branding, integration, and workflow endpoints.
- Company Admin read access returns `200` for dashboard, departments, branches, invitations, users, roles, settings, integrations, and workflow settings.
- An unauthenticated dashboard request returns `401`.
- A Company Employee receives `403` for company settings, roles, integrations, and workflow settings.
- The Day-40 verification sessions were removed after testing; maintenance mode is off.
- Tenant isolation, role assignment, role CRUD, invitation security, settings persistence, integration/workflow isolation, and dashboard aggregation are covered by the automated service suites.

## Security boundaries

- Company identity is derived from the validated JWT/session context.
- Company-scoped repositories must never accept client-provided tenant identity as authority.
- Frontend visibility is not an authorization boundary; protected backend operations enforce permissions and return `401` or `403` as appropriate.
- Cross-tenant role, department, branch, user, invitation, settings, integration, workflow, and dashboard access is rejected.

## Decisions and deferred scope

- Finance remains an explicit unavailable/planned dashboard state until its roadmap phase supplies a finance model.
- Google Drive, Slack, Stripe OAuth/credentials, and the automation engine remain future scope; Day-38 stores no provider credentials.
- Company color customization remains deferred; current Loopless theme values remain authoritative.

## Manual browser evidence still required

Automated builds and API checks do not prove visual behavior. Before marking the checkpoint fully complete, manually verify the complete Company Admin journey in a real browser at desktop, tablet, and mobile widths: login/logout, sidebar, dashboard states, invitations, department/branch forms, user assignment, role editor, settings/branding, integrations/workflows, persistence after refresh, modal overflow, and browser-console cleanliness.

## Result

The automated and API portion of Day-40 passes. Final Day-40 status remains **manual browser verification required** until the visual and complete invitation-email journey are actually executed.

## Complete verification status

| Checkpoint | Status | Evidence |
| --- | --- | --- |
| Protected Company Admin APIs | PASS | Real authenticated requests returned `200` for dashboard, departments, branches, invitations, users, roles, settings, integrations, and workflows. |
| Authentication enforcement | PASS | Real unauthenticated dashboard request returned `401`; malformed/typed/rotated JWT and login-protection tests pass. |
| Invalid credentials and logout journey | MANUAL REQUIRED | Authentication services are covered by tests, but a real Company Admin credential login and logout sequence was not executed in this checkpoint run. |
| Dashboard tenant KPIs | PASS | Company A/B, empty state, missing context, missing permission, and cross-tenant selection tests pass. Finance is intentionally unavailable until its roadmap phase. |
| Invitation security and account creation | PASS (AUTOMATED) | Tenant-bound hashed token, duplicate, invalid/expired, permission, and account-creation tests pass. |
| Invitation email/browser acceptance E2E | MANUAL REQUIRED | No new invitation email was sent or accepted in a real browser during this run. |
| Departments and branches | PASS (AUTOMATED) | CRUD/soft-disable, validation, duplicate, permission, and cross-tenant tests pass. |
| User role/department/branch assignment | PASS (AUTOMATED) | Atomic assignment, tenant-bound options, employee denial, and missing-permission tests pass. |
| Role CRUD and permission enforcement | PASS (AUTOMATED) | Create, update, permission catalog, duplicate, safe delete, cross-tenant rejection, allow, and `403` denial tests pass. |
| Company settings and branding persistence | PASS (AUTOMATED) | Tenant-scoped reads, grouped updates, validation, branding removal, audit, and restricted-role tests pass. |
| Integrations and workflow persistence | PASS (AUTOMATED + API) | Tenant persistence/isolation tests pass; real Company Admin reads return `200`, Employee reads return `403`. |
| Audit coverage | PASS (AUTOMATED) | Invitation, organization, assignment, role, settings, and integration services assert audit events; audit serialization/pagination tests pass. |
| Responsive UI and browser console | MANUAL REQUIRED | Browser-control connection was unavailable; visual behavior was not claimed as tested. |
| Engineering | PASS | 123 backend tests; Black, Ruff, MyPy; five frontend type-check/lint/build jobs; `git diff --check`; current migrations; healthy Docker services. |
| Repository clean | NOT APPLICABLE | The repository contains intentional uncommitted Day-37–39 work; no commit or push was performed. |
