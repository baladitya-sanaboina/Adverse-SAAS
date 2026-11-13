# Database Foundation

## Architecture

Loopless uses PostgreSQL as its database. Prisma is the authoritative schema, migration, generated-client, and seed tool. The FastAPI runtime uses a centralized Psycopg connection pool to query PostgreSQL.

```text
Prisma schema -> Prisma migration -> PostgreSQL
                                      ^
                                      |
FastAPI -> Psycopg connection pool ---+
```

Docker Compose runs the `migrations` service after PostgreSQL becomes healthy. That service applies pending Prisma migrations and idempotently seeds the five system roles. The backend starts only after the migration service completes successfully.

## Core Models

### Company (`companies`)

- UUID primary key
- name
- unique company code
- subscription plan
- status (`ACTIVE`, `INACTIVE`, `SUSPENDED`, or `PENDING`)
- optional contact email
- created and updated timestamps

### Role (`roles`)

- UUID primary key
- unique name
- unique stable code
- created and updated timestamps

The initial seed contains only:

- Platform Owner
- Developer
- Company Admin
- Company Employee
- Company Client

### User (`users`)

- UUID primary key
- name
- unique email
- password hash storage field
- status (`ACTIVE`, `INACTIVE`, or `SUSPENDED`)
- nullable company reference for platform users
- required role reference
- created and updated timestamps

The database stores RBAC modules, permissions, and role-permission mappings. Password verification, authentication, login, and user-session behavior are not implemented yet.

### Registration Audit (`registration_audits`)

- UUID primary key
- action (`USER_CREATED` or `COMPANY_CREATED`)
- required creator reference
- optional created-user reference
- optional company reference
- assigned role code for user creation
- created timestamp

Registration writes the resource and its audit record in one transaction. Passwords are stored only as salted scrypt hashes; confirmation passwords are never persisted.

## Relationships

```text
Company 1 ---- 0..* User * ---- 1 Role
```

- One company can contain many users.
- A user can belong to one company; the reference is nullable for platform-level users.
- Every user has exactly one role.
- Company and role deletion is restricted while referenced by users.

## Naming Conventions

- Tables and database columns use `snake_case` and plural table names.
- Prisma models and enums use `PascalCase`.
- Prisma fields use `camelCase` and map to snake-case database columns.
- Primary and foreign identifiers use PostgreSQL UUID values.
- Migration directories use `YYYYMMDDHHMMSS_description` names.

## Migration Workflow

Create a development migration after changing `prisma/schema.prisma`:

```bash
docker compose -f docker/docker-compose.yml run --rm migrations \
  npm run prisma:migrate:dev -- --name <change_name>
```

For the Docker development stack, build and start from the repository root:

```bash
docker compose -f docker/docker-compose.yml up --build
```

Apply existing migrations and seed roles manually inside Compose:

```bash
docker compose -f docker/docker-compose.yml run --rm migrations
```

Inspect migration state:

```bash
docker compose -f docker/docker-compose.yml run --rm migrations npx prisma migrate status
```

Never edit an already-applied migration. Create a new migration for every future schema change.

## Subscription Foundation (Day-24)

The `20260805170000_add_subscription_management` migration adds:

- `subscription_plans` for plan metadata, prices, lifecycle status, and ordering.
- `subscription_plan_features` for enabled/disabled plan capabilities.
- `subscription_plan_limits` for finite values or `NULL` (unlimited).
- `company_subscriptions` for the company's current plan and activation/expiration dates.
- `subscription_audits` for actor, company, plan, action, and timestamp history.

One company has zero or one current subscription; a plan can serve many companies. Plan deletion is intentionally not exposed because subscriptions and audit history retain plan references.

## Subscription Enforcement Foundation (Day-25)

The `20260805193000_add_subscription_enforcement` migration adds `company_usage_metrics`, `subscription_usage_alerts`, and `subscription_enforcement_audits`. Migration `20260805194500_backfill_company_subscriptions` maps legacy company plan labels to active relational subscriptions. New company onboarding writes that relation transactionally. Employee and client counts are derived from company users; project and storage counters are reserved for their future module write paths. See `SubscriptionEnforcement.md` for thresholds and enforcement rules.

## Client Domain Foundation (Day-44)

Migration `20260816120000_client_domain_foundation` adds tenant-owned `clients` and one-to-many `client_contacts`. Client codes are unique per Company, contact emails are unique per Client, and lookup indexes cover Company/status, Company/name, Client/status, and primary-contact access. The authenticated JWT supplies the Company context; Client APIs never accept a frontend tenant identifier. See `ClientManagement.md` for the API, RBAC, primary-contact, and tenant-isolation contract.

## CRM Foundation (Day-46)

Migration `20260816160000_crm_leads_opportunities` adds tenant-owned `leads`, `opportunities`, and `crm_audits`. Migration `20260816161000_crm_company_admin_permissions` maps the existing Company Admin role to CRM view/create/edit actions. Leads have an optional Client and required Employee owner. Opportunities have a required Client, optional originating Lead, required Employee owner, `DECIMAL(18,2)` value, three-letter currency, derived OPEN/CLOSED status, and optional expected close date. Composite indexes support Company/status, Company/source, Company/stage, and Company/owner queries; Client and Lead foreign keys support relationship lookups. See `CRMFoundation.md` for the API, RBAC, audit, and cross-tenant relationship contract.
# Day-48 Client history

The Client domain now includes `client_notes`, `client_feedback`, and `client_activities`. Each table is directly tenant-bound through `company_id`, belongs to one `client_id`, and records a creator or actor from `users`.

```text
companies 1 ── * clients
clients   1 ── * client_notes       * ── 1 users (creator)
clients   1 ── * client_feedback    * ── 1 users (creator)
clients   1 ── * client_activities  * ── 1 users (actor)
```

Tenant/client/time indexes support deterministic newest-first history reads. Client deletion cascades its history; user deletion remains restricted while authored business history exists.
