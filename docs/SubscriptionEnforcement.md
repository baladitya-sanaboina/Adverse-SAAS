# Subscription Enforcement

## Scope

Day-25 adds subscription enforcement and usage monitoring. It does not include payments or invoice generation.

## Architecture

```text
Company operation
  -> SubscriptionEnforcementService
  -> Active company subscription
  -> Feature or resource limit
  -> Allow / deny
  -> Warning and audit persistence
```

The centralized service is reusable by future CRM, Projects, Finance, Documents, AI, and API modules. Employee and client registration now call the service before creating a user.

## APIs

- `GET /platform/companies/{company_id}/usage` returns the active plan, enabled features, employee/client/project/storage usage, remaining capacity, warning state, and upgrade recommendation.
- `POST /platform/companies/{company_id}/subscription/validate` validates exactly one `feature_code` or `resource_code` plus an optional requested increment.

Both endpoints require authentication and `COMPANIES_VIEW`. Platform Owner retains its documented bypass; Developer access is evaluated from assigned permissions on every request.

## Feature validation

Feature codes are read from `subscription_plan_features`. Disabled or missing features return `allowed=false`, an upgrade recommendation, and a `FEATURE_BLOCKED` audit event. Initial feature codes include CRM, Finance, Reports, White Label, API Access, and AI Features.

## Usage tracking and limits

| Resource | Usage source | Limit code |
| --- | --- | --- |
| Employees | Company users with `COMPANY_EMPLOYEE` role | `MAX_EMPLOYEES` |
| Clients | Company users with `COMPANY_CLIENT` role | `MAX_CLIENTS` |
| Projects | `company_usage_metrics.projects_used` | `MAX_PROJECTS` |
| Storage | `company_usage_metrics.storage_used_bytes` | `MAX_STORAGE_GB` |

`null` limits are unlimited. Employee and client creation is rejected with `SUBSCRIPTION_LIMIT_REACHED` before database insertion when the next record would exceed the assigned limit. Project and storage validators are ready for their future create/upload flows.

## Warning rules

- Below 80%: `OK`
- 80–89.9%: `WARNING`
- 90–99.9%: `HIGH_USAGE`
- 100%: `LIMIT_REACHED`
- Null limit: `UNLIMITED`

Active warnings are stored in `subscription_usage_alerts`. A reached limit returns `upgrade_recommended=true`; no payment action is performed.

## Audit events

`subscription_enforcement_audits` records the company, actor where available, current plan, feature/resource, usage, limit, and timestamp. Events include `PLAN_VALIDATED`, `FEATURE_BLOCKED`, `LIMIT_EXCEEDED`, and `UPGRADE_RECOMMENDED`.

## Database workflow

Apply migrations `20260805193000_add_subscription_enforcement` and `20260805194500_backfill_company_subscriptions` using the documented Prisma migration command. They create usage metrics, warning, and enforcement audit tables and connect legacy company plan labels to active relational subscriptions. New company onboarding creates that subscription relation in the same transaction.
