# Subscription Management

Day-24 adds centralized subscription-plan management for the Platform Owner. It does not include payment processing, invoicing, billing gateways, or usage metering.

## Architecture

```text
Platform Owner -> Subscription Plan -> Features + Limits -> Company Subscription
```

`subscription_plans` stores plan identity, pricing, status, and display order. Feature flags and limits are normalized into `subscription_plan_features` and `subscription_plan_limits`. A company has at most one current record in `company_subscriptions`.

## Plan APIs

- `POST /platform/subscription-plans` creates a plan and its configuration.
- `GET /platform/subscription-plans` supports pagination, search, status filtering, and sorting.
- `GET /platform/subscription-plans/{plan_id}` returns one configured plan.
- `PUT /platform/subscription-plans/{plan_id}` updates plan metadata, features, limits, and status.
- `PATCH /platform/companies/{company_id}/plan` assigns or changes a company's plan.

Operations use granular `SUBSCRIPTIONS` permissions: list/details require `VIEW`, creation requires `CREATE`, updates require `EDIT`, and company assignment requires `ASSIGN`. The Platform Owner retains the existing platform-level bypass. Duplicate plan codes return `409`, missing resources return `404`, malformed identifiers or bodies return `422`, and unauthorized access returns `401/403`.

## Features and Limits

Feature codes are uppercase keys with explicit enabled/disabled values. Limit codes are uppercase keys whose values are non-negative integers. A `null` limit means unlimited. The seeded Starter, Professional, and Enterprise definitions are baseline data and remain editable through the Platform Owner UI.

The subscription validation service resolves a company's current active plan and answers feature/limit checks. Day-24 provides this reusable foundation; usage counters and runtime enforcement begin on Day-25.

## Assignment and Plan Changes

Assignment stores activation and optional expiration dates. Display order determines whether a change is classified as an upgrade, downgrade, or same-tier change. Inactive plans cannot be assigned. Company details expose current plan, status, dates, enabled features, and limits.

Downgrades are configuration-valid when the target plan is active. Actual resource-usage comparisons are intentionally deferred to Day-25 because usage monitoring is outside Day-24.

## Audit Trail

`subscription_audits` records the actor, plan, optional company, action, and timestamp for plan creation, update, activation, deactivation, assignment, upgrade, downgrade, and change.

## UI

The Platform Owner Subscriptions page provides list, search, status filter, sort, pagination, create, view, edit, activation controls, feature switches, and unlimited-aware limit inputs. Company Details includes the current subscription and plan-change control. Existing dashboard shell, breadcrumbs, palette, and responsive behavior are preserved.

## Validation

```bash
docker compose -f docker/docker-compose.yml run --rm migrations
docker compose -f docker/docker-compose.yml exec backend python -m unittest discover -s tests -v
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run build
```
