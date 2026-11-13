# Company Management

## Scope

Day-23 gives Platform Owners centralized tenant visibility and status control. Developers may access the same APIs only when the required `COMPANIES` RBAC permission is assigned. Subscription CRUD and billing are outside this milestone.

## APIs

- `GET /platform/companies` supports pagination, name/code/admin-email search, status and plan filters, and newest/oldest/A–Z/Z–A sorting.
- `GET /platform/companies/{company_id}` returns company information, default Company Admin, subscription, user statistics, timestamps, and recent management activity.
- `PATCH /platform/companies/{company_id}/status` accepts `ACTIVE`, `INACTIVE`, `SUSPENDED`, or `PENDING`.

## Status lifecycle

Only `ACTIVE` companies permit their users to authenticate. Changing a company to `INACTIVE`, `SUSPENDED`, or `PENDING` revokes all active tenant sessions. Reactivation permits a new login.

## Authorization

Platform Owners bypass Company permission checks. Developers require `COMPANIES:VIEW` for list/details and `COMPANIES:EDIT` for status controls. Permissions are queried at request time, so changes apply without waiting for JWT expiry.

## Auditing

`company_management_audits` stores the actor, company, action, previous status, new status, and timestamp for company views and status transitions.

## Frontend

The Platform Owner Companies page provides summary statistics, responsive listing, debounced search, filters, sorting, pagination, detail view, recent activity, status badges, confirmation dialogs, loading states, errors, and empty states within the existing Loopless dashboard shell.
