# Platform Management

## Milestone

Day-29 validates the integrated Platform Management architecture covering Days 21–28. Day-30 is the final Platform Owner checkpoint: the complete authentication, Developer, tenant, subscription, settings, onboarding, audit, and operational workflow must pass before Company Administration begins.

## Architecture and ownership

The Platform Owner operates the platform dashboard, developer lifecycle, company lifecycle, subscriptions, global settings, and onboarding. Developers can access only explicitly assigned modules/actions. A Company Admin manages only the company identified by the validated JWT `company_id`. Employees and Clients cannot modify platform or company configuration.

The API layer validates request/response contracts, services enforce authorization and business rules, repositories own parameterized database access and transactions, PostgreSQL stores durable state/audits, Redis supports security and runtime controls, Mailpit validates local SMTP delivery, and the five Next.js applications consume the single FastAPI backend.

## Validated modules

| Module | Scope | Operations |
| --- | --- | ---: |
| Platform Dashboard | Statistics, recent activity, system overview, quick actions | 1 |
| Developer Management | Create, list, detail, update, status and permissions | 5 |
| Company Management | List, detail, status, search/filter/pagination | 3 |
| Subscription Management & Enforcement | Plans, assignment, usage and validation | 7 |
| Platform Settings | Branding, SMTP, defaults and maintenance | 7 |
| Company Onboarding | Transactional provisioning and summary | 2 |
| Company Settings | Tenant branding, contact, regional and preferences | 4 |
| Audit Logs | Read-only, searchable inventory across eight critical audit sources | 1 |

Swagger version `0.22.0` documents 55 total backend operations; 30 belong to the validated Platform Management phase. The Platform Owner Backend page reads the same OpenAPI document and health response, so its inventory is synchronized rather than manually duplicated.

## Subscription flow

Plans define enabled features and employee, client, project, storage, and AI limits. Company assignment supports upgrade/downgrade while preserving a single active company subscription. Enforcement runs server-side: hidden UI is not treated as authorization. Unlimited values bypass numeric limits; finite values produce usage thresholds, limit errors, audit events, and upgrade recommendations.

## Settings and onboarding flow

Platform Settings apply global defaults and contain encrypted SMTP credentials, branding, maintenance behavior, and onboarding defaults. Company Settings are isolated per JWT company and never update the global record. Branding uploads validate MIME type, signature, and size before writing to isolated storage paths.

Onboarding performs Company, Subscription, Company Admin, tenant defaults, role/permission snapshot, audit events, and welcome-mail state in one transaction. A failure rolls back partial records. Welcome mail never contains a password.

## RBAC, security, and tenant isolation

- Bearer JWT validation includes user, role, company, session, issue, and expiry context.
- Active sessions are checked server-side; status changes revoke applicable sessions.
- Platform Owner-only services reject other roles even when called directly.
- Developer APIs enforce current database permissions on every request.
- Company Settings derive the tenant solely from JWT context and reject Platform Owner, Developer, Employee, Client, and anonymous access.
- `/tenant/context` requires authentication and rejects a header tenant that does not exactly match the JWT company.
- Subscription limits and feature availability are enforced in backend services.
- Passwords use salted scrypt hashes; token material is not stored in plaintext.
- Uploads accept only supported, signature-verified images within configured size limits.
- CORS, security headers, request validation, generic authentication errors, rate limiting, and account lock remain enabled.

## Audit coverage

Critical Developer creation/update/status/permission actions, Company status actions, Subscription plan/assignment/enforcement actions, Onboarding steps, Platform Settings changes, and Company Settings changes include actor, target/company, action, details, and timestamp. Audit writes occur inside the related transaction where atomicity is required.

`GET /platform/audit-logs` gives the Platform Owner a read-only, paginated view across Developer, Company, Subscription, Platform Settings, Onboarding, Company Settings, Registration, and Subscription Enforcement events. Anonymous requests return `401`; authenticated non-Platform roles return `403`. The `/logs` UI provides search, category filtering, ordering, loading, error, empty, pagination, desktop, tablet, and mobile states using the existing Loopless theme.

## Performance review

List endpoints use bounded pagination and parameterized filters. Dashboard aggregation avoids loading rows into application memory. Detail endpoints use indexed UUID/unique keys. Day-29 adds composite indexes for the primary filtered/sorted paths:

- `users(role_id, status, created_at)`
- `companies(status, created_at)`
- `companies(subscription_plan, status)`
- `subscription_plans(status, display_order)`

API timing validation is performed locally against Docker services and documented with the verification result rather than adding production profiling behavior.

## Operational validation

The `/health` response exposes every underlying service plus the aggregate `platform_management` milestone. Healthy completion requires PostgreSQL, Redis, Mailpit, RBAC, tenant middleware, authentication, dashboard, developer/company/subscription services, global settings, onboarding, company settings, and the live audit query. The completed aggregate reports `checkpoint: day-30-passed` only when every dependency is ready.

## Day-30 checkpoint validation

- Platform Owner login, protected access, logout/session behavior, dashboard counts, health, and quick actions are validated.
- Developer create/login, immediate permission removal/restoration, deactivate/reactivate, and session enforcement are validated.
- Developer-authorized transactional onboarding creates the Company, Starter subscription, Company Admin, tenant defaults, verification mail, and welcome mail; an intentional duplicate-admin failure leaves no partial Company.
- Company status transitions through Pending, Inactive, Suspended, and Active; non-active login is denied and prior sessions are revoked.
- Company Admin verification, login, `/users/me`, settings persistence, and cross-tenant denial are validated.
- Subscription feature validation allows enabled features and returns a blocked result plus upgrade recommendation for disabled features. Numeric and unlimited limits remain covered by the enforcement regression suite.
- Maintenance mode blocks Company access while preserving Platform Owner access, then restores access when disabled. SMTP test delivery is confirmed through Mailpit.
- Critical checkpoint actions are visible through the Audit Logs endpoint with actor, action, company/target, and timestamp.

Validation commands:

```bash
docker compose -f docker/docker-compose.yml up -d
docker compose -f docker/docker-compose.yml ps
curl http://localhost:8000/health
curl http://localhost:8000/openapi.json
```

Quality gates are Black, Ruff, MyPy, backend unit/integration tests, Prisma migration deployment, Prettier, and format/lint/type-check/build for all five frontends. Git publication remains a separate explicit user action.
